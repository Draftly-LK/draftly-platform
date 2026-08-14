import { ProfileScreen } from "@/components/support/profile-screen";
import { isClerkConfigured } from "@/lib/auth/clerk";

export default function ProfilePage() {
  return <ProfileScreen clerkEnabled={isClerkConfigured()} />;
}
