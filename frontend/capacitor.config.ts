/// <reference types="@capacitor/keyboard" />

import type { CapacitorConfig } from "@capacitor/cli";

const serverUrl = process.env.CAP_SERVER_URL;

const config: CapacitorConfig = {
  appId: "com.agent2.mobile",
  appName: "智能出行助手",
  webDir: "dist",
  bundledWebRuntime: false,
  plugins: {
    Keyboard: {
      resizeOnFullScreen: true,
    },
  },
  ...(serverUrl
    ? {
        server: {
          url: serverUrl,
          cleartext: true,
        },
      }
    : {}),
};

export default config;
