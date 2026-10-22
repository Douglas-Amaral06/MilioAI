export interface SupportState {
  vt_stage?: "idle" | "selection" | "active";
  selected_card_code?: string;
  stage?: "idle" | "confirmation" | "selection" | "contact";
  asked?: boolean;
  selected_instructor_id?: string | null;
}
export type SupportAction = {
  kind:
    | "instructor_known"
    | "instructor_unknown"
    | "instructor_select"
    | "instructor_cancel"
    | "instructor_resume"
    | "card_select"
    | "card_change";
  instructor_id?: string;
  benefit_code?: string;
};
export interface Message {
  contacts?: InstitutionalContact[];
  id: string;
  role: "user" | "assistant";
  status?: "processing" | "complete" | "failed" | "cancelled";
  sources?: DocumentReference[];
  outcome?: string;
  topicId?: string | null;
  questionId?: string | null;
  content: string;
  createdAt: string;
}
export interface InstitutionalContact {
  contact_id: string;
  team: string;
  domain: string;
  phone: string;
  phone_digits: string;
  channel: "whatsapp" | "phone";
  whatsapp_enabled?: boolean;
  whatsapp_validation_status?: string;
  url: string | null;
  label: string;
  email: string;
  email_url: string | null;
  validation_status: string;
  availability_status: string;
  provenance: {
    version: string;
    directory_version: string;
    institutionally_approved: boolean;
  };
}
export interface DocumentReference {
  id: string;
  title: string;
  document_id?: string;
  version?: string;
  section?: string;
  validation_only?: boolean;
  page?: number;
  chunk?: number;
  is_test?: boolean;
  url?: string;
  excerpt?: string;
}
export interface Conversation {
  supportState?: SupportState;
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  draft: string;
  topicId?: string | null;
  messages: Message[];
  references: DocumentReference[];
}
export interface WorkspaceState {
  version: 1;
  conversations: Conversation[];
  activeId: string | null;
  draft: string;
}
