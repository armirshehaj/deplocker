export function getFromLocalStorage(key: string) {
  return localStorage.getItem(key);
}

export function setOnLocalStorage(key: string, value: string) {
  localStorage.setItem(key, value);
}

export function removeFromLocalStorage(key: string) {
  localStorage.removeItem(key);
}

export function clearLocalStorage() {
  localStorage.clear();
}
