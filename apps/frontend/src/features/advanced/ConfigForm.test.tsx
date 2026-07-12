// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ConfigForm } from "@/features/advanced/ConfigForm";
import * as configApi from "@/api/config";
import type { SystemConfig } from "@/types/admin";

vi.mock("@/api/config");

const sample: SystemConfig = {
  rag_top_k: 20,
  graph_top_k: 20,
  hybrid_candidate_k: 30,
  hybrid_rrf_k: 60,
  rerank_top_k: 8,
  bm25_top_k: 20,
  graph_max_seed_entities: 5,
  graph_max_chunks_per_seed: 20,
  graph_hub_source_count_threshold: 80,
  graph_max_context_items: 12,
  graph_max_path_hops: 3,
  graph_path_hit_weight: 1.5,
  llm_temperature: 0.0,
  updated_at: "2026-07-11T00:00:00Z",
};

function renderForm() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ConfigForm />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ConfigForm", () => {
  it("nạp giá trị server vào các ô", async () => {
    vi.mocked(configApi.getSystemConfig).mockResolvedValue(sample);
    renderForm();
    const rag = (await screen.findByLabelText("RAG top-k")) as HTMLInputElement;
    expect(rag.value).toBe("20");
    expect((screen.getByLabelText("Temperature") as HTMLInputElement).value).toBe("0");
  });

  it("chặn temperature ngoài [0,2] và vô hiệu nút lưu", async () => {
    vi.mocked(configApi.getSystemConfig).mockResolvedValue(sample);
    renderForm();
    const temp = (await screen.findByLabelText("Temperature")) as HTMLInputElement;
    fireEvent.change(temp, { target: { value: "3" } });
    expect(screen.getByText("Phải ≤ 2.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Lưu/ })).toBeDisabled();
  });

  it("chặn rerank_top_k > hybrid_candidate_k (ràng buộc chéo)", async () => {
    vi.mocked(configApi.getSystemConfig).mockResolvedValue(sample);
    renderForm();
    const candidate = (await screen.findByLabelText("Hybrid candidate-k")) as HTMLInputElement;
    fireEvent.change(candidate, { target: { value: "5" } }); // rerank=8 > 5
    expect(screen.getByText("Không được lớn hơn Hybrid candidate-k.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Lưu/ })).toBeDisabled();
  });

  it("lưu gọi API với patch số + hiện banner hiệu lực 60 giây", async () => {
    vi.mocked(configApi.getSystemConfig).mockResolvedValue(sample);
    vi.mocked(configApi.updateSystemConfig).mockResolvedValue({ ...sample, rag_top_k: 15 });
    renderForm();
    const rag = (await screen.findByLabelText("RAG top-k")) as HTMLInputElement;
    fireEvent.change(rag, { target: { value: "15" } });
    fireEvent.click(screen.getByRole("button", { name: /Lưu/ }));

    await waitFor(() => expect(configApi.updateSystemConfig).toHaveBeenCalled());
    // react-query truyền (variables, context) -> chỉ soi tham số đầu (patch).
    expect(vi.mocked(configApi.updateSystemConfig).mock.calls[0][0]).toEqual(
      expect.objectContaining({ rag_top_k: 15, llm_temperature: 0 }),
    );
    expect(await screen.findByText(/hiệu lực trong tối đa 60 giây/)).toBeInTheDocument();
  });
});
