import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../../lib/apiClient";
import type {
  EmailComposeResponse,
  EmailTemplate,
  EmailTemplateField,
  GeneralEmailPreview,
} from "../../../types/email";
import * as applicationsApi from "../applications/api";
import * as api from "./api";
import { EmailPage } from "./EmailPage";

let mockRoles: string[] = ["ORG_ADMIN"];
vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({ accessToken: "test-token", user: { roles: mockRoles } }),
}));

const recipientName: EmailTemplateField = {
  key: "candidate_name",
  label: "Recipient name",
  input_type: "text",
  required: false,
  options: [],
  placeholder: "",
};
const role: EmailTemplateField = {
  key: "job_title",
  label: "Role / position",
  input_type: "text",
  required: true,
  options: [],
  placeholder: "",
};

const templates: EmailTemplate[] = [
  {
    key: "GENERAL",
    name: "General recruitment message",
    description: "A clean, professional starting point for any other message.",
    fields: [],
    general_fields: [recipientName],
  },
  {
    key: "REJECTION",
    name: "Application update – not moving forward",
    description: "Respectfully let the candidate know their application will not proceed.",
    fields: [],
    general_fields: [recipientName, role],
  },
  {
    key: "ASSESSMENT_INVITATION",
    name: "Assessment invitation",
    description: "Send the candidate their personal link to the assigned online assessment.",
    fields: [],
    general_fields: null,
  },
];

function composed(overrides: Partial<EmailComposeResponse> = {}): EmailComposeResponse {
  return {
    template_key: "GENERAL",
    subject: "A message from Acme Corp",
    body: "Dear Sir or Madam,\n\nI am writing to you on behalf of Acme Corp.",
    variables: {},
    missing_required: [],
    ...overrides,
  };
}

const preview: GeneralEmailPreview = {
  to: ["dana@example.com"],
  cc: ["boss@example.com"],
  bcc: [],
  reply_to: "admin@acme.dev",
  subject: "A message from Acme Corp",
  html: "<!DOCTYPE html><html><body><p>Dear Sir or Madam,</p></body></html>",
  text: "Dear Sir or Madam,",
  has_call_to_action: false,
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <EmailPage />
    </QueryClientProvider>,
  );
}

async function pickTemplate(name: string) {
  const select = await screen.findByLabelText("Template");
  await waitFor(() => expect(screen.getByRole("option", { name })).toBeInTheDocument());
  const option = screen.getByRole("option", { name }) as HTMLOptionElement;
  fireEvent.change(select, { target: { value: option.value } });
}

describe("EmailPage (general email)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockRoles = ["ORG_ADMIN"];
    vi.spyOn(applicationsApi, "listEmailTemplates").mockResolvedValue(templates);
  });

  it("opens an unaddressed composer with recipient fields and nothing sent", async () => {
    const compose = vi.spyOn(api, "composeGeneralEmail");
    const send = vi.spyOn(api, "sendGeneralEmail");

    renderPage();

    expect(await screen.findByRole("heading", { name: "Email" })).toBeInTheDocument();
    expect(screen.getByLabelText(/^To/)).toBeInTheDocument();
    expect(screen.getByLabelText("Cc")).toBeInTheDocument();
    expect(screen.getByLabelText("Bcc")).toBeInTheDocument();
    expect(screen.getByLabelText("Template")).toHaveValue("");
    expect(screen.getByRole("button", { name: "Preview" })).toBeDisabled();
    expect(compose).not.toHaveBeenCalled();
    expect(send).not.toHaveBeenCalled();
  });

  it("greys out templates that need an application", async () => {
    renderPage();
    await screen.findByLabelText("Template");
    await waitFor(() => screen.getByRole("option", { name: /General recruitment message/ }));

    const unavailable = screen.getByRole("option", { name: /Assessment invitation/ }) as HTMLOptionElement;
    expect(unavailable).toBeDisabled();
    expect(unavailable.textContent).toMatch(/needs an application/);
  });

  it("loads a template, shows the recipient/role fields and re-fills as they change", async () => {
    const compose = vi.spyOn(api, "composeGeneralEmail").mockImplementation(async (request) =>
      composed({
        template_key: "REJECTION",
        subject: `Update – ${request.variables.job_title ?? "{{job_title}}"}`,
        body: `Dear ${request.variables.candidate_name || "Sir or Madam"},`,
        missing_required: request.variables.job_title ? [] : ["job_title"],
      }),
    );

    renderPage();
    await pickTemplate("Application update – not moving forward");

    expect(await screen.findByDisplayValue("Update – {{job_title}}")).toBeInTheDocument();
    expect(screen.getByLabelText("Recipient name")).toBeInTheDocument();
    expect(screen.getByLabelText(/Role \/ position/)).toBeInTheDocument();
    expect(screen.getByText(/Fill in the required details above/)).toBeInTheDocument();
    expect(compose).toHaveBeenCalledWith(
      { template_key: "REJECTION", variables: {} },
      "test-token",
    );

    fireEvent.change(screen.getByLabelText("Recipient name"), { target: { value: "Dana" } });
    fireEvent.change(screen.getByLabelText(/Role \/ position/), { target: { value: "Data Analyst" } });

    expect(await screen.findByDisplayValue("Update – Data Analyst")).toBeInTheDocument();
    expect(screen.getByLabelText("Message")).toHaveValue("Dear Dana,");
  });

  it("previews then sends to the typed To/Cc/Bcc recipients, then resets", async () => {
    vi.spyOn(api, "composeGeneralEmail").mockResolvedValue(composed());
    const previewSpy = vi.spyOn(api, "previewGeneralEmail").mockResolvedValue(preview);
    const sendSpy = vi.spyOn(api, "sendGeneralEmail").mockResolvedValue({
      sent: true,
      to: ["dana@example.com"],
      cc: ["boss@example.com"],
      bcc: [],
      subject: "Edited subject",
    });

    renderPage();
    fireEvent.change(await screen.findByLabelText(/^To/), {
      target: { value: "dana@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Cc"), { target: { value: "boss@example.com" } });
    await pickTemplate("General recruitment message");
    await screen.findByDisplayValue("A message from Acme Corp");

    fireEvent.change(screen.getByLabelText("Subject"), { target: { value: "Edited subject" } });
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Custom text." } });
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));

    const frame = (await screen.findByTitle("Email preview")) as HTMLIFrameElement;
    const expectedDraft = {
      template_key: "GENERAL",
      subject: "Edited subject",
      body: "Custom text.",
      variables: {},
      to: ["dana@example.com"],
      cc: ["boss@example.com"],
      bcc: [],
    };
    expect(previewSpy).toHaveBeenCalledWith(expectedDraft, "test-token");
    expect(frame.getAttribute("sandbox")).toBe("");
    expect(screen.getByText("boss@example.com")).toBeInTheDocument();
    expect(sendSpy).not.toHaveBeenCalled(); // previewing is not sending

    fireEvent.click(screen.getByRole("button", { name: "Send email" }));

    await waitFor(() => expect(sendSpy).toHaveBeenCalledWith(expectedDraft, "test-token"));
    expect(
      await screen.findByText(/Email sent to dana@example.com, boss@example.com/),
    ).toBeInTheDocument();
    // The composer is back to a clean state.
    expect(screen.getByLabelText(/^To/)).toHaveValue("");
    expect(screen.getByLabelText("Template")).toHaveValue("");
  });

  it("accepts several recipients separated by commas, semicolons or spaces", async () => {
    vi.spyOn(api, "composeGeneralEmail").mockResolvedValue(composed());
    const previewSpy = vi.spyOn(api, "previewGeneralEmail").mockResolvedValue(preview);

    renderPage();
    fireEvent.change(await screen.findByLabelText(/^To/), {
      target: { value: "a@example.com, b@example.com; c@example.com d@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Bcc"), { target: { value: "<hidden@example.com>" } });
    await pickTemplate("General recruitment message");
    await screen.findByDisplayValue("A message from Acme Corp");
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));

    await screen.findByTitle("Email preview");
    expect(previewSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        to: ["a@example.com", "b@example.com", "c@example.com", "d@example.com"],
        bcc: ["hidden@example.com"],
      }),
      "test-token",
    );
  });

  it("rejects a missing or malformed recipient before calling the server", async () => {
    vi.spyOn(api, "composeGeneralEmail").mockResolvedValue(composed());
    const previewSpy = vi.spyOn(api, "previewGeneralEmail");

    renderPage();
    await pickTemplate("General recruitment message");
    await screen.findByDisplayValue("A message from Acme Corp");

    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    expect(await screen.findByText("Enter at least one recipient in To.")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/^To/), {
      target: { value: "good@example.com, not-an-email" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    expect(
      await screen.findByText("Not a valid email address: not-an-email"),
    ).toBeInTheDocument();
    expect(previewSpy).not.toHaveBeenCalled();
  });

  it("shows the server's reason when the preview is refused", async () => {
    vi.spyOn(api, "composeGeneralEmail").mockResolvedValue(composed());
    vi.spyOn(api, "previewGeneralEmail").mockRejectedValue(
      new ApiError("The email still contains unfilled placeholders ({{job_title}}).", 422, "unresolved_placeholders"),
    );

    renderPage();
    fireEvent.change(await screen.findByLabelText(/^To/), { target: { value: "dana@example.com" } });
    await pickTemplate("General recruitment message");
    await screen.findByDisplayValue("A message from Acme Corp");
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));

    expect(await screen.findByText(/still contains unfilled placeholders/)).toBeInTheDocument();
    expect(screen.queryByTitle("Email preview")).not.toBeInTheDocument();
  });

  it("reports an SMTP problem honestly and does not claim success", async () => {
    vi.spyOn(api, "composeGeneralEmail").mockResolvedValue(composed());
    vi.spyOn(api, "previewGeneralEmail").mockResolvedValue(preview);
    vi.spyOn(api, "sendGeneralEmail").mockRejectedValue(
      new ApiError("Email is not configured.", 503, "email_not_configured"),
    );

    renderPage();
    fireEvent.change(await screen.findByLabelText(/^To/), { target: { value: "dana@example.com" } });
    await pickTemplate("General recruitment message");
    await screen.findByDisplayValue("A message from Acme Corp");
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    await screen.findByTitle("Email preview");
    fireEvent.click(screen.getByRole("button", { name: "Send email" }));

    expect(await screen.findByText("Email is not configured.")).toBeInTheDocument();
    expect(screen.queryByText(/Email sent to/)).not.toBeInTheDocument();
  });

  it("Cancel clears the form and sends nothing", async () => {
    vi.spyOn(api, "composeGeneralEmail").mockResolvedValue(composed());
    const send = vi.spyOn(api, "sendGeneralEmail");

    renderPage();
    fireEvent.change(await screen.findByLabelText(/^To/), { target: { value: "dana@example.com" } });
    await pickTemplate("General recruitment message");
    await screen.findByDisplayValue("A message from Acme Corp");
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.getByLabelText(/^To/)).toHaveValue("");
    expect(screen.getByLabelText("Template")).toHaveValue("");
    expect(send).not.toHaveBeenCalled();
  });

  it("is available to a recruiter but shows no composer to other roles", async () => {
    mockRoles = ["RECRUITER"];
    const { unmount } = renderPage();
    expect(await screen.findByLabelText("Template")).toBeInTheDocument();
    unmount();

    for (const role of ["HIRING_MANAGER", "INTERVIEWER"]) {
      mockRoles = [role];
      const view = renderPage();
      expect(await screen.findByText("You do not have permission to send email.")).toBeInTheDocument();
      expect(screen.queryByLabelText("Template")).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/^To/)).not.toBeInTheDocument();
      view.unmount();
    }
  });
});
