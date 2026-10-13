import { describe, it, expect, beforeEach } from "vitest";
import {
  getFromLocalStorage,
  setOnLocalStorage,
  removeFromLocalStorage,
  clearLocalStorage,
} from "@/lib/utils/local-storage";

describe("localStorage utils", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  describe("setOnLocalStorage / getFromLocalStorage", () => {
    it("stores and retrieves a value", () => {
      setOnLocalStorage("key", "value");
      expect(getFromLocalStorage("key")).toBe("value");
    });

    it("returns null for a key that was never set", () => {
      expect(getFromLocalStorage("nonexistent")).toBeNull();
    });

    it("overwrites an existing value", () => {
      setOnLocalStorage("key", "first");
      setOnLocalStorage("key", "second");
      expect(getFromLocalStorage("key")).toBe("second");
    });
  });

  describe("removeFromLocalStorage", () => {
    it("removes the key", () => {
      setOnLocalStorage("key", "value");
      removeFromLocalStorage("key");
      expect(getFromLocalStorage("key")).toBeNull();
    });

    it("does not throw when key does not exist", () => {
      expect(() => removeFromLocalStorage("nonexistent")).not.toThrow();
    });
  });

  describe("clearLocalStorage", () => {
    it("removes all keys", () => {
      setOnLocalStorage("a", "1");
      setOnLocalStorage("b", "2");
      clearLocalStorage();
      expect(getFromLocalStorage("a")).toBeNull();
      expect(getFromLocalStorage("b")).toBeNull();
    });
  });
});
