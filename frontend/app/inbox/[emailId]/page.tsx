import { EmailDetail } from "@/components/email-detail";
export default async function EmailPage({
  params,
}: {
  params: Promise<{ emailId: string }>;
}) {
  const { emailId } = await params;
  return <EmailDetail emailId={emailId} />;
}
