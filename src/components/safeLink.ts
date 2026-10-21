export function safeLink(value: string): boolean {
  return (
    /^(https?:\/\/|mailto:|tel:)/i.test(value) &&
    !/\s/.test(value) &&
    !Array.from(value).some((character) => character.charCodeAt(0) < 32)
  );
}
