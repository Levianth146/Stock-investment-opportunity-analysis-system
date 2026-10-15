import { assertUnchanged, readStartSnap, snapAll } from "./helpers/quotaGuard";

async function globalTeardown() {
  const before = readStartSnap();
  const after = snapAll();
  assertUnchanged(before, after);
}

export default globalTeardown;
