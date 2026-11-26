// HARMLESS DEMO of a malicious npm package. Do not publish.
//
// npm runs "postinstall" scripts automatically on `npm install`, which is how
// many real npm attacks start. This only records the NAMES of secret-looking
// environment variables, never their values, to a local file, with no network
// calls. A real one would send the values somewhere.
const fs = require("node:fs");
const os = require("node:os");

const looksSecret = ["TOKEN", "SECRET", "PASSWORD", "API_KEY", "ACCESS_KEY"];
const names = Object.keys(process.env)
  .filter((k) => looksSecret.some((w) => k.toUpperCase().includes(w)))
  .sort();
fs.writeFileSync(
  process.env.DEMO_LOOT_FILE || "demo-loot.txt",
  `Install-time code ran as ${os.userInfo().username}.\n` +
    `It could read these environment variables: ${names.join(", ") || "none"}\n`,
);
