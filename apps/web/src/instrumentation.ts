export async function register() {
  if (process.env.NEXT_RUNTIME !== "nodejs") return;

  const { auth } = await import("./auth");
  const context = await auth.$context;
  await context.runMigrations();
}
