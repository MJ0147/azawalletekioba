"use client";

import { CopilotKit } from "@copilotkit/react-core";
import { CopilotSidebar } from "@copilotkit/react-ui";

export default function CopilotProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const publicApiKey = process.env.NEXT_PUBLIC_COPILOTKIT_PUBLIC_API_KEY;

  if (!publicApiKey) {
    return <>{children}</>;
  }

  return (
    <CopilotKit publicApiKey={publicApiKey}>
      {children}
      <CopilotSidebar />
    </CopilotKit>
  );
}