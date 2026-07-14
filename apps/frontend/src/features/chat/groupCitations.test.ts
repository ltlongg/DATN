import { describe, expect, it } from "vitest";
import { groupCitations } from "@/features/chat/groupCitations";
import type { Citation } from "@/types";

function cit(chunkId: string, headingPath: string[]): Citation {
  return { chunk_id: chunkId, heading_path: headingPath };
}

const COLONIAL = "Thời kì thuộc địa";
const CAN_VUONG = "7. Phong trào Cần vương";

describe("groupCitations", () => {
  it("gộp 2 citation cùng mục thành 1 nhóm 2 chip", () => {
    const { groups } = groupCitations([
      cit("c-1", [COLONIAL, CAN_VUONG, "Lê Thành Phương"]),
      cit("c-2", [COLONIAL, CAN_VUONG, "Bãi Sậy"]),
      cit("c-3", [COLONIAL, CAN_VUONG, "Lê Thành Phương"]),
    ]);
    expect(groups).toHaveLength(2);
    expect(groups[0].title).toBe("Lê Thành Phương");
    expect(groups[0].chips.map((c) => c.n)).toEqual([1, 3]);
    expect(groups[1].chips.map((c) => c.n)).toEqual([2]);
  });

  it("giữ số chip theo thứ tự GỐC, không đánh số lại sau khi gộp", () => {
    const { groups } = groupCitations([
      cit("c-1", ["A", "X"]),
      cit("c-2", ["A", "Y"]),
      cit("c-3", ["A", "X"]),
    ]);
    // Nhóm X gom chip 1 và 3 — nếu đánh số lại sẽ thành [1,2] và phá liên kết với "[3]"
    // mà câu trả lời nhắc tới.
    expect(groups[0].chips.map((c) => c.n)).toEqual([1, 3]);
    expect(groups[1].chips.map((c) => c.n)).toEqual([2]);
  });

  it("chip trỏ đúng citation của nó (1 chip = 1 chunk)", () => {
    const { groups } = groupCitations([
      cit("c-1", ["A", "X"]),
      cit("c-2", ["A", "X"]),
    ]);
    expect(groups[0].chips.map((c) => c.citation.chunk_id)).toEqual(["c-1", "c-2"]);
  });

  it("rút tiền tố chung ra commonPath, tiêu đề nhóm chỉ còn phần riêng", () => {
    const { groups, commonPath } = groupCitations([
      cit("c-1", [COLONIAL, CAN_VUONG, "Lê Thành Phương"]),
      cit("c-2", [COLONIAL, CAN_VUONG, "Bãi Sậy"]),
    ]);
    expect(commonPath).toEqual([COLONIAL, CAN_VUONG]);
    expect(groups.map((g) => g.title)).toEqual(["Lê Thành Phương", "Bãi Sậy"]);
  });

  it("giữ nhiều cấp còn lại trong tiêu đề khi tiền tố chung ngắn", () => {
    const { groups, commonPath } = groupCitations([
      cit("c-1", ["A", "B", "C"]),
      cit("c-2", ["A", "D", "E"]),
    ]);
    expect(commonPath).toEqual(["A"]);
    expect(groups.map((g) => g.title)).toEqual(["B › C", "D › E"]);
  });

  it("nguồn rải nhiều chương -> commonPath rỗng, tiêu đề là full path", () => {
    const { groups, commonPath } = groupCitations([
      cit("c-1", [COLONIAL, "Cần vương"]),
      cit("c-2", ["Thời kì cộng hoà", "Biên giới Tây Nam"]),
    ]);
    expect(commonPath).toEqual([]);
    expect(groups.map((g) => g.title)).toEqual([
      `${COLONIAL} › Cần vương`,
      "Thời kì cộng hoà › Biên giới Tây Nam",
    ]);
  });

  it("mọi citation cùng một mục lá -> lùi 1 cấp để cấp cuối làm tiêu đề", () => {
    const { groups, commonPath } = groupCitations([
      cit("c-1", [COLONIAL, CAN_VUONG, "Bãi Sậy"]),
      cit("c-2", [COLONIAL, CAN_VUONG, "Bãi Sậy"]),
    ]);
    // Tiền tố chung = trọn path -> tiêu đề sẽ rỗng nếu không lùi.
    expect(commonPath).toEqual([COLONIAL, CAN_VUONG]);
    expect(groups).toHaveLength(1);
    expect(groups[0].title).toBe("Bãi Sậy");
    expect(groups[0].chips.map((c) => c.n)).toEqual([1, 2]);
  });

  it("một nhóm là tiền tố của nhóm kia -> lùi 1 cấp, không nhóm nào rỗng tiêu đề", () => {
    const { groups, commonPath } = groupCitations([
      cit("c-1", ["A", "B"]),
      cit("c-2", ["A", "B", "C"]),
    ]);
    expect(commonPath).toEqual(["A"]);
    expect(groups.map((g) => g.title)).toEqual(["B", "B › C"]);
  });

  it("path 1 cấp giống nhau -> lùi về commonPath rỗng, vẫn có tiêu đề", () => {
    const { groups, commonPath } = groupCitations([cit("c-1", ["A"]), cit("c-2", ["A"])]);
    expect(commonPath).toEqual([]);
    expect(groups[0].title).toBe("A");
  });

  it("heading_path rỗng -> nhóm 'Không rõ mục', chip vẫn giữ nguyên", () => {
    const { groups, commonPath } = groupCitations([cit("c-1", []), cit("c-2", ["A", "B"])]);
    expect(commonPath).toEqual([]);
    expect(groups[0].title).toBe("Không rõ mục");
    expect(groups[0].chips.map((c) => c.citation.chunk_id)).toEqual(["c-1"]);
    expect(groups[1].title).toBe("A › B");
  });

  it("heading có khoảng trắng không làm vỡ khoá gộp", () => {
    const { groups } = groupCitations([
      cit("c-1", ["Thời kì thuộc địa", "Khởi nghĩa Bãi Sậy"]),
      cit("c-2", ["Thời kì thuộc địa", "Khởi nghĩa Bãi Sậy"]),
    ]);
    expect(groups).toHaveLength(1);
    expect(groups[0].chips).toHaveLength(2);
  });

  it("mảng rỗng -> không nhóm, không commonPath", () => {
    expect(groupCitations([])).toEqual({ groups: [], commonPath: [] });
  });
});
