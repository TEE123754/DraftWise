import type { Metadata } from "next";
import Link from "next/link";
import { AuthFrame } from "@/components/auth-frame";
import { Button } from "@/components/ui/button";
import SignInForm from "./sign-in-form";
export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in to your DraftWise workspace.",
  robots: { index: false, follow: false },
};
export default function SignInPage() {
  return (
    <AuthFrame>
      <p className="auth-kicker">WELCOME TO DRAFTWISE</p>
      <h1>Sign in to your workspace</h1>
      <p className="auth-description">
        Enter your work email to receive a secure sign-in link. No password
        needed.
      </p>
      <SignInForm />
      <div className="auth-alternative">
        <p>Just taking a look?</p>
        <Button asChild variant="secondary" className="w-full">
          <Link href="/demo">Try the demo without signing in</Link>
        </Button>
        <small>Prepared shipment samples. No account required.</small>
      </div>
      <p className="auth-legal">
        By signing in you agree to our <Link href="/terms">Terms</Link> and{" "}
        <Link href="/privacy">Privacy Policy</Link>.
      </p>
    </AuthFrame>
  );
}
