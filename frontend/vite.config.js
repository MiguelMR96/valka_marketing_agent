import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// V1 DEMO IMPLEMENTATION — built for a deadline, not yet understood by
// Miguel. Do not extend without a rebuild pass. See build spec Definition
// of Done.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
});
