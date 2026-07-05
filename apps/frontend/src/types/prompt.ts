/** Types quản lý Prompt (Item 2). Mirror apps/backend/app/schemas/prompt.py. */

export interface PromptListItem {
  key: string;
  grp: string;
  title: string;
  description: string | null;
  active_version_no: number | null;
  version_count: number;
  updated_at: string;
}

export interface PromptVersionMeta {
  version_no: number;
  note: string | null;
  status: string;
  created_by: string | null;
  created_at: string;
  promoted_by: string | null;
  promoted_at: string | null;
}

export interface PromptDetail {
  key: string;
  grp: string;
  title: string;
  description: string | null;
  updated_at: string;
  production_content: string | null;
  versions: PromptVersionMeta[];
}

export interface PromptVersionContent {
  version_no: number;
  content: string;
  status: string;
}

export interface CreateVersionInput {
  content: string;
  note?: string | null;
}
