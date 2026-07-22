"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const theme = require("../textbook-theme.js");
const toc = require("../textbook-toc.js");

const fakeClassList = (...initial) => {
  const values = new Set(initial);
  return {
    contains: (name) => values.has(name),
    add: (name) => values.add(name),
    remove: (name) => values.delete(name),
    toggle: (name, force) => {
      if (force === undefined ? !values.has(name) : force) values.add(name);
      else values.delete(name);
    },
  };
};

test("theme values are normalized before they reach the DOM", () => {
  assert.equal(theme.normalizeTheme("dark"), "dark");
  assert.equal(theme.normalizeTheme("light"), "light");
  assert.equal(theme.normalizeTheme("system"), null);
  assert.equal(theme.normalizeTheme(null), null);
});

test("theme toggle and Quarto persistence keep their established mapping", () => {
  assert.equal(theme.nextTheme("dark"), "light");
  assert.equal(theme.nextTheme("light"), "dark");
  assert.equal(theme.quartoThemePreference("dark"), "alternate");
  assert.equal(theme.quartoThemePreference("light"), "default");
  assert.equal(theme.THEME_STORAGE_KEY, "textbook-color-scheme");
  assert.equal(theme.QUARTO_THEME_STORAGE_KEY, "quarto-color-scheme");
});

test("applying dark theme updates Quarto sheets, body, button, and storage", () => {
  const stored = new Map();
  const alternate = { rel: "disabled-stylesheet" };
  const primary = { rel: "stylesheet" };
  const quartoToggle = { classList: fakeClassList() };
  const body = { classList: fakeClassList("quarto-light") };
  const icon = { className: "" };
  const buttonAttributes = new Map();
  const button = {
    querySelector: () => icon,
    setAttribute: (name, value) => buttonAttributes.set(name, value),
  };
  const doc = {
    body,
    querySelectorAll: (selector) => {
      if (selector.includes("quarto-color-alternate")) return [alternate];
      if (selector === "link.quarto-color-scheme:not(.quarto-color-alternate)") {
        return [primary];
      }
      if (selector === ".quarto-color-scheme-toggle") return [quartoToggle];
      return [];
    },
  };
  const win = {
    localStorage: {
      getItem: (key) => stored.get(key) || null,
      setItem: (key, value) => stored.set(key, value),
    },
    Event: class FakeEvent {},
    dispatchEvent: () => {},
  };

  theme.applyTheme("dark", button, doc, win);

  assert.equal(alternate.rel, "stylesheet");
  assert.equal(primary.rel, "stylesheet");
  assert.equal(body.classList.contains("quarto-dark"), true);
  assert.equal(body.classList.contains("quarto-light"), false);
  assert.equal(quartoToggle.classList.contains("alternate"), true);
  assert.equal(stored.get(theme.THEME_STORAGE_KEY), "dark");
  assert.equal(stored.get(theme.QUARTO_THEME_STORAGE_KEY), "alternate");
  assert.equal(buttonAttributes.get("aria-pressed"), "true");
  assert.equal(icon.className, "bi bi-sun-fill");
});

test("TOC fragments are decoded safely", () => {
  assert.equal(toc.targetIdFromHref("#section-1"), "section-1");
  assert.equal(toc.targetIdFromHref("#%E7%AC%AC%E4%B8%80%E8%8A%82"), "第一节");
  assert.equal(toc.targetIdFromHref("#bad%escape"), null);
  assert.equal(toc.targetIdFromHref(""), null);
});

test("TOC context follows the active heading and its top-level branch", () => {
  const firstChapter = { id: "first" };
  const secondChapter = { id: "second" };
  const entries = [
    { id: "first-title", top: 0, topLevelItem: firstChapter },
    { id: "first-detail", top: 180, topLevelItem: firstChapter },
    { id: "second-title", top: 420, topLevelItem: secondChapter },
    { id: "second-detail", top: 620, topLevelItem: secondChapter },
  ];

  const firstContext = toc.selectTocContext(entries, 260);
  assert.equal(firstContext.activeEntry.id, "first-detail");
  assert.equal(firstContext.activeTopLevelItem, firstChapter);
  assert.deepEqual(
    toc.branchVisibility([firstChapter, secondChapter], firstContext.activeTopLevelItem),
    [true, false]
  );

  const secondContext = toc.selectTocContext(entries, 500);
  assert.equal(secondContext.activeEntry.id, "second-title");
  assert.equal(secondContext.activeTopLevelItem, secondChapter);
  assert.deepEqual(
    toc.branchVisibility([firstChapter, secondChapter], secondContext.activeTopLevelItem),
    [false, true]
  );
});

test("TOC context opens the first branch before the first heading crosses the marker", () => {
  const firstChapter = { id: "first" };
  const entries = [{ id: "first-title", top: 120, topLevelItem: firstChapter }];
  const context = toc.selectTocContext(entries, 0);

  assert.equal(context.activeEntry.id, "first-title");
  assert.equal(context.activeTopLevelItem, firstChapter);
});

test("empty TOC input has no active item or visible branch", () => {
  assert.deepEqual(toc.selectTocContext([], 100), {
    activeEntry: null,
    activeTopLevelItem: null,
  });
  assert.deepEqual(toc.branchVisibility([], null), []);
});

test("TOC DOM update hides every secondary branch except the active one", () => {
  const firstItem = { id: "first" };
  const secondItem = { id: "second" };
  const firstList = {
    parentElement: firstItem,
    hidden: true,
    classList: fakeClassList(),
  };
  const secondList = {
    parentElement: secondItem,
    hidden: false,
    classList: fakeClassList("textbook-toc-branch-open"),
  };
  const root = { querySelectorAll: () => [firstList, secondList] };

  toc.updateSecondaryEntries(root, firstItem);

  assert.equal(firstList.hidden, false);
  assert.equal(firstList.classList.contains("textbook-toc-branch-open"), true);
  assert.equal(secondList.hidden, true);
  assert.equal(secondList.classList.contains("textbook-toc-branch-open"), false);
});

test("header loader keeps theme, TOC, and general UI in deterministic order", () => {
  const template = fs.readFileSync(
    path.join(__dirname, "..", "theme-toggle.html"),
    "utf8"
  );
  const themePosition = template.indexOf('"textbook-theme.js"');
  const tocPosition = template.indexOf('"textbook-toc.js"');
  const uiPosition = template.indexOf('"textbook-ui.js"');

  assert.ok(themePosition >= 0 && themePosition < tocPosition);
  assert.ok(tocPosition < uiPosition);
  assert.match(template, /script\.async\s*=\s*false/);
});
