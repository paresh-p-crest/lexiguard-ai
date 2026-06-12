/** Copy root documentation.md into Vite public/ for Vercel static hosting. */
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const uiRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const projectRoot = join(uiRoot, "..");
const src = join(projectRoot, "documentation.md");
const destDir = join(uiRoot, "public");
const dest = join(destDir, "documentation.md");

mkdirSync(destDir, { recursive: true });
copyFileSync(src, dest);
console.log("Copied documentation.md → lexiguard-ui/public/documentation.md");
