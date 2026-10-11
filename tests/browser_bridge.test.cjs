const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

function fixture() {
  const chrome = {
    alarms: {create() {}, onAlarm: {addListener() {}}},
    runtime: {onMessage: {addListener() {}}, onStartup: {addListener() {}}},
    storage: {local: {async get() {return {}}}},
  };
  const context = vm.createContext({chrome, URL, crypto: require('node:crypto').webcrypto,
    location: {href: 'https://example.com/', hostname: 'example.com'},
    getComputedStyle: () => ({visibility: 'visible'}),
    CSS: {escape: x => x}, NodeFilter: {SHOW_TEXT: 4}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../extensions/june-browser-bridge/background.js'), 'utf8'), context);
  return context;
}

test('URL guard rejects protected protocols, administration and credentials', () => {
  const c = fixture();
  for (const url of ['file:///private', 'http://127.0.0.1:8765/api/trust', 'https://u:p@example.com', 'https://example.com/#access_token=abc']) {
    assert.throws(() => c.safeURL(url));
  }
  assert.equal(c.safeURL('https://example.com/path'), 'https://example.com/path');
});

test('page navigation race fails before reading DOM', () => {
  const c = fixture();
  assert.throws(() => c.pageAction('read', {expectedURL: 'https://old.example/'}), /navigated/);
});

test('read supplies a usable selector for controls without IDs', () => {
  const c = fixture();
  const button = {tagName: 'BUTTON', nodeType: 1, id: '', innerText: 'Continue', name: '',
    getAttribute: () => null, getClientRects: () => [1], closest: () => null, parentElement: null};
  c.document = {body: {}, title: 'Fixture', createTreeWalker: () => ({nextNode: () => null}),
    querySelectorAll: () => [button]};
  const result = c.pageAction('read', {expectedURL: c.location.href});
  assert.equal(result.controls[0].selector, 'button:nth-of-type(1)');
});

test('ambiguous and disabled controls never receive clicks', () => {
  const c = fixture();
  const button = {disabled: true, getClientRects: () => [1], getAttribute: () => null};
  c.document = {querySelector: () => button, querySelectorAll: () => [button, button]};
  const args = {expectedURL: c.location.href, selector: 'button', action: 'click'};
  assert.throws(() => c.pageAction('apply', args), /disabled/);
  button.disabled = false;
  assert.throws(() => c.pageAction('apply', args), /ambiguous/);
});

test('apply tickets are consumed even when target changes', async () => {
  const c = fixture();
  vm.runInContext("tickets.set('one', {tab: 1, fingerprint:'old', expires:Date.now()+10000}); inject=async()=>({fingerprint:'changed'});", c);
  await assert.rejects(c.dispatch('apply', {ticket: 'one'}), /Target changed/);
  await assert.rejects(c.dispatch('apply', {ticket: 'one'}), /Expired action ticket/);
});
