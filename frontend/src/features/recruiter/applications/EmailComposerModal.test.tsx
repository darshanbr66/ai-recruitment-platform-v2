import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../../lib/apiClient";
import type {
  EmailComposeResponse,
  EmailPreview,
  EmailTemplate,
  EmailTemplateKey,
} from "../../../types/email";
import * as api from "./api";
import { EmailComposerModal } from "./EmailComposerModal";

const templates: EmailTemplate[] = [
  {
    key: "APPLICATION_RECEIVED",
    name: "Application received",
    description: "Thank the candidate and confirm their application has been received.",
    fields: [],
    general_fields: null,
  },
  {
    key: "INTERVIEW_INVITATION",
    name: "Interview invitation",
    description: "Invite the candidate to an interview round.",
    fields: [
      { key: "interview_date", label: "Interview date", input_type: "date", required: true, options: [], placeholder: "" },
      { key: "interview_mode", label: "Interview mode", input_type: "select", required: true, options: ["Video call", "In person"], placeholder: "" },
      { key: "meeting_link", label: "Meeting link", input_type: "url", required: false, options: [], placeholder: "" },
    ],
    general_fields: null,
  },
  {
    key: "ASSESSMENT_INVITATION",
    name: "Assessment invitation",
    description: "Send the candidate their assessment link.",
    fields: [],
    general_fields: null,
  },
];

function composed(key: EmailTemplateKey, overrides: Partial<EmailComposeResponse> = {}): EmailComposeResponse {
  return {
    template_key: key,
    subject: `Subject for ${key}`,
    body: `Dear Cara Candidate,\n\nBody for ${key}.`,
    variables: {},
    missing_required: [],
    ...overrides,
  };
}

const preview: EmailPreview = {
  to: "cara@example.com",
  reply_to: "riya@acme.dev",
  subject: "Subject for APPLICATION_RECEIVED",
  html: "<!DOCTYPE html><html><body><p>Dear Cara Candidate,</p></body></html>",
  text: "Dear Cara Candidate,",
  has_call_to_action: false,
};

function renderModal(props: { initialTemplate?: EmailTemplateKey; onSent?: () => void; onClose?: () => void } = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <EmailComposerModal
        applicationId="app-1"
        candidateName="Cara Candidate"
        candidateEmail="cara@example.com"
        accessToken="test-token"
        initialTemplate={props.initialTemplate}
        onClose={props.onClose ?? vi.fn()}
        onSent={props.onSent ?? vi.fn()}
      />
    </QueryClientProvider>,
  );
}

async function pickTemplate(name: string) {
  const select = await screen.findByLabelText("Template");
  await waitFor(() => expect(screen.getByRole("option", { name })).toBeInTheDocument());
  fireEvent.change(select, { target: { value: templates.find((t) => t.name === name)!.key } });
}

describe("EmailComposerModal", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "listEmailTemplates").mockResolvedValue(templates);
  });

  it("starts with no template, sends nothing, and says so", async () => {
    const compose = vi.spyOn(api, "composeEmail");
    const send = vi.spyOn(api, "sendEmail");

    renderModal();

    expect(await screen.findByLabelText("Template")).toHaveValue("");
    expect(screen.getByText(/Nothing is\s+emailed automatically/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Preview" })).toBeDisabled();
    expect(compose).not.toHaveBeenCalled();
    expect(send).not.toHaveBeenCalled();
  });

  it("loads the chosen template with the known details filled in", async () => {
    const compose = vi
      .spyOn(api, "composeEmail")
      .mockResolvedValue(composed("APPLICATION_RECEIVED"));

    renderModal();
    await pickTemplate("Application received");

    expect(await screen.findByDisplayValue("Subject for APPLICATION_RECEIVED")).toBeInTheDocument();
    expect(screen.getByLabelText("Message")).toHaveValue(
      "Dear Cara Candidate,\n\nBody for APPLICATION_RECEIVED.",
    );
    expect(compose).toHaveBeenCalledWith(
      "app-1",
      { template_key: "APPLICATION_RECEIVED", variables: {} },
      "test-token",
    );
  });

  it("opens straight on the template it was launched with", async () => {
    const compose = vi
      .spyOn(api, "composeEmail")
      .mockResolvedValue(composed("ASSESSMENT_INVITATION"));

    renderModal({ initialTemplate: "ASSESSMENT_INVITATION" });

    expect(await screen.findByDisplayValue("Subject for ASSESSMENT_INVITATION")).toBeInTheDocument();
    expect(compose).toHaveBeenCalledTimes(1);
  });

  it("previews and sends exactly the text the recruiter edited, only when Send is clicked", async () => {
    vi.spyOn(api, "composeEmail").mockResolvedValue(composed("APPLICATION_RECEIVED"));
    const previewSpy = vi.spyOn(api, "previewEmail").mockResolvedValue(preview);
    const sendSpy = vi
      .spyOn(api, "sendEmail")
      .mockResolvedValue({ sent: true, to: "cara@example.com", subject: "My edited subject" });
    const onSent = vi.fn();

    renderModal({ onSent });
    await pickTemplate("Application received");
    await screen.findByDisplayValue("Subject for APPLICATION_RECEIVED");

    fireEvent.change(screen.getByLabelText("Subject"), { target: { value: "My edited subject" } });
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Dear Cara,\n\nEdited." } });
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));

    const frame = (await screen.findByTitle("Email preview")) as HTMLIFrameElement;
    const expectedDraft = {
      template_key: "APPLICATION_RECEIVED",
      subject: "My edited subject",
      body: "Dear Cara,\n\nEdited.",
      variables: {},
    };
    expect(previewSpy).toHaveBeenCalledWith("app-1", expectedDraft, "test-token");
    // The rendered email is untrusted markup: fully sandboxed.
    expect(frame.getAttribute("sandbox")).toBe("");
    expect(frame.getAttribute("srcdoc")).toBe(preview.html);
    expect(screen.getByText("riya@acme.dev")).toBeInTheDocument();

    // Previewing is not sending.
    expect(sendSpy).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Send email" }));
    await waitFor(() => expect(onSent).toHaveBeenCalledTimes(1));
    expect(sendSpy).toHaveBeenCalledWith("app-1", expectedDraft, "test-token");
  });

  it("does not send when cancelled", async () => {
    vi.spyOn(api, "composeEmail").mockResolvedValue(composed("APPLICATION_RECEIVED"));
    vi.spyOn(api, "previewEmail").mockResolvedValue(preview);
    const sendSpy = vi.spyOn(api, "sendEmail");
    const onClose = vi.fn();

    renderModal({ onClose });
    await pickTemplate("Application received");
    await screen.findByDisplayValue("Subject for APPLICATION_RECEIVED");
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    await screen.findByTitle("Email preview");
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onClose).toHaveBeenCalled();
    expect(sendSpy).not.toHaveBeenCalled();
  });

  it("shows template-specific fields and re-fills the email as they change", async () => {
    const compose = vi.spyOn(api, "composeEmail").mockImplementation(async (_id, request) =>
      composed("INTERVIEW_INVITATION", {
        body: `Date: ${request.variables.interview_date ?? "{{interview_date}}"}`,
        missing_required: request.variables.interview_date ? [] : ["interview_date", "interview_mode"],
      }),
    );

    renderModal();
    await pickTemplate("Interview invitation");

    expect(await screen.findByLabelText(/Interview date/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Interview mode/)).toBeInTheDocument();
    expect(screen.getByLabelText("Meeting link")).toBeInTheDocument();
    expect(await screen.findByDisplayValue("Date: {{interview_date}}")).toBeInTheDocument();
    expect(screen.getByText(/Fill in the required details above/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/Interview date/), { target: { value: "2026-09-25" } });

    expect(await screen.findByDisplayValue("Date: 2026-09-25")).toBeInTheDocument();
    expect(compose).toHaveBeenLastCalledWith(
      "app-1",
      { template_key: "INTERVIEW_INVITATION", variables: { interview_date: "2026-09-25" } },
      "test-token",
    );
    await waitFor(() =>
      expect(screen.queryByText(/Fill in the required details above/)).not.toBeInTheDocument(),
    );
  });

  it("never overwrites text the recruiter has edited, until they reset to the template", async () => {
    const compose = vi.spyOn(api, "composeEmail").mockImplementation(async (_id, request) =>
      composed("INTERVIEW_INVITATION", { body: `Date: ${request.variables.interview_date ?? "TBD"}` }),
    );

    renderModal();
    await pickTemplate("Interview invitation");
    await screen.findByDisplayValue("Date: TBD");

    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "My own wording." } });
    fireEvent.change(screen.getByLabelText(/Interview date/), { target: { value: "2026-09-25" } });
    await new Promise((resolve) => setTimeout(resolve, 450));

    expect(screen.getByLabelText("Message")).toHaveValue("My own wording.");
    expect(compose).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getAllByRole("button", { name: "Reset to template" })[0]);

    expect(await screen.findByDisplayValue("Date: 2026-09-25")).toBeInTheDocument();
    expect(compose).toHaveBeenCalledTimes(2);
  });

  it("stays on the editor and explains why when the preview is rejected", async () => {
    vi.spyOn(api, "composeEmail").mockResolvedValue(composed("INTERVIEW_INVITATION"));
    vi.spyOn(api, "previewEmail").mockRejectedValue(
      new ApiError(
        "The email still contains unfilled placeholders ({{interview_date}}).",
        422,
        "unresolved_placeholders",
      ),
    );

    renderModal();
    await pickTemplate("Interview invitation");
    await screen.findByDisplayValue("Subject for INTERVIEW_INVITATION");
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));

    expect(await screen.findByText(/still contains unfilled placeholders/)).toBeInTheDocument();
    expect(screen.queryByTitle("Email preview")).not.toBeInTheDocument();
  });

  it("reports an SMTP problem honestly and does not claim success", async () => {
    vi.spyOn(api, "composeEmail").mockResolvedValue(composed("APPLICATION_RECEIVED"));
    vi.spyOn(api, "previewEmail").mockResolvedValue(preview);
    vi.spyOn(api, "sendEmail").mockRejectedValue(
      new ApiError("Email is not configured.", 503, "email_not_configured"),
    );
    const onSent = vi.fn();

    renderModal({ onSent });
    await pickTemplate("Application received");
    await screen.findByDisplayValue("Subject for APPLICATION_RECEIVED");
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    await screen.findByTitle("Email preview");
    fireEvent.click(screen.getByRole("button", { name: "Send email" }));

    expect(await screen.findByText("Email is not configured.")).toBeInTheDocument();
    expect(onSent).not.toHaveBeenCalled();
  });
});
