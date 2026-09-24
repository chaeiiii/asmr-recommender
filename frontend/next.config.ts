import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Keep the repository's root AGENTS.md as the maintained project instructions.
  agentRules: false,
};

export default nextConfig;
