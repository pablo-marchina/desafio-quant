import { StartupProfile } from "@/components/startup-profile";

export default function StartupPage({ params }: { params: { id: string } }) {
  return <StartupProfile startupId={decodeURIComponent(params.id)} />;
}
