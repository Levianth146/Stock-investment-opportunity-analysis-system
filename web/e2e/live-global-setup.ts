/**
 * Setup cho suite live: chỉ cảnh báo, không chặn thay đổi quota.
 */
async function liveGlobalSetup() {
  console.warn(
    "[e2e:live] Suite này gọi LLM thật và có thể thay đổi data/llm_cache (_quota_state / _debate_budget). Không chạy kèm suite mặc định.",
  );
}

export default liveGlobalSetup;
