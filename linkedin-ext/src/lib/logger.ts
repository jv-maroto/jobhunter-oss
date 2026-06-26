// Logger minimal centralizado. Útil para silenciar en producción.

const PREFIX = "[JobHunter]";

export const log = {
  info: (...args: unknown[]) => console.log(PREFIX, ...args),
  warn: (...args: unknown[]) => console.warn(PREFIX, ...args),
  error: (...args: unknown[]) => console.error(PREFIX, ...args),
  debug: (...args: unknown[]) => console.debug(PREFIX, ...args)
};
