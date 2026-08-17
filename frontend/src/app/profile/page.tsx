import { ProfileScreen } from "@/components/support/profile-screen";
import { isApiEnabled } from "@/lib/api/client";
import { isClerkConfigured } from "@/lib/auth/clerk";

export default function ProfilePage() {
  return <ProfileScreen clerkEnabled={isClerkConfigured()} apiEnabled={isApiEnabled()} />;
}
