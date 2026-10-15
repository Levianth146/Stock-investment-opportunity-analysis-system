import { writeStartSnap } from "./helpers/quotaGuard";

async function globalSetup() {
  writeStartSnap();
}

export default globalSetup;
