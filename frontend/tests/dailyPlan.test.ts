// Tests for the "Plan for today" rules, run with Node's built-in test runner: npm test
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { doneCount, msUntilNextUtcDay, parseStore, recordFor, utcDay, withCheckIn, withManual } from '../src/services/dailyPlan.ts'

const AT = '2026-11-15T09:30:00.000Z'
const none = { sleep: false, mood: false }

test('the mission day changes at 00:00 UTC, whatever the local time zone', () => {
  assert.equal(utcDay(Date.parse('2026-11-15T23:59:59.999Z')), '2026-11-15')
  assert.equal(utcDay(Date.parse('2026-11-16T00:00:00.000Z')), '2026-11-16')
  assert.equal(utcDay(Date.parse('2026-11-16T01:30:00+02:00')), '2026-11-15') // 23:30 UTC
  assert.equal(msUntilNextUtcDay(Date.parse('2026-11-15T23:59:00Z')), 60_000)
  assert.equal(msUntilNextUtcDay(Date.parse('2026-12-31T00:00:00Z')), 24 * 3_600_000)
})

test('nothing is done before an assessed check-in', () => {
  const r = recordFor({}, 'commander', '2026-11-15')
  assert.equal(r.checkin, null)
  assert.equal(doneCount(r), 0)
})

test('an assessed check-in completes the check-in, and only the optional fields it included', () => {
  const store = withCheckIn({}, 'commander', '2026-11-15', { sleep: true, mood: false }, false, AT)
  const r = recordFor(store, 'commander', '2026-11-15')
  assert.deepEqual(r.checkin, { at: AT, example: false })
  assert.equal(r.sleep, true)
  assert.equal(r.mood, false)
  assert.equal(r.review, false)
  assert.equal(doneCount(r), 2)
})

test('a later check-in without an optional field does not undo it on the same day', () => {
  let store = withCheckIn({}, 'commander', '2026-11-15', { sleep: true, mood: true }, true, AT)
  store = withCheckIn(store, 'commander', '2026-11-15', none, false, '2026-11-15T15:00:00.000Z')
  const r = recordFor(store, 'commander', '2026-11-15')
  assert.equal(r.sleep && r.mood, true)
  assert.deepEqual(r.checkin, { at: '2026-11-15T15:00:00.000Z', example: false })
})

test('progress is kept separately for each astronaut', () => {
  const store = withCheckIn({}, 'commander', '2026-11-15', none, false, AT)
  assert.equal(doneCount(recordFor(store, 'commander', '2026-11-15')), 1)
  assert.equal(doneCount(recordFor(store, 'flight_engineer_1', '2026-11-15')), 0)
})

test('tasks done on an earlier UTC day do not count today, and a new day starts empty', () => {
  let store = withCheckIn({}, 'commander', '2026-11-15', { sleep: true, mood: true }, false, AT)
  store = withManual(store, 'commander', '2026-11-15', 'review', true)
  assert.equal(doneCount(recordFor(store, 'commander', '2026-11-15')), 4)
  assert.equal(doneCount(recordFor(store, 'commander', '2026-11-16')), 0)
  store = withManual(store, 'commander', '2026-11-16', 'review', true)
  const today = recordFor(store, 'commander', '2026-11-16')
  assert.equal(today.checkin, null)
  assert.equal(today.sleep || today.mood, false)
  assert.equal(doneCount(today), 1)
})

test('the manual task can be ticked and unticked', () => {
  let store = withManual({}, 'commander', '2026-11-15', 'review', true)
  assert.equal(recordFor(store, 'commander', '2026-11-15').review, true)
  store = withManual(store, 'commander', '2026-11-15', 'review', false)
  assert.equal(recordFor(store, 'commander', '2026-11-15').review, false)
})

test('saved progress round-trips through JSON', () => {
  const store = withManual(withCheckIn({}, 'commander', '2026-11-15', { sleep: false, mood: true }, true, AT), 'commander', '2026-11-15', 'review', true)
  assert.deepEqual(parseStore(JSON.stringify(store)), store)
})

test('malformed saved data is dropped, never trusted', () => {
  assert.deepEqual(parseStore(null), {})
  assert.deepEqual(parseStore('not json'), {})
  assert.deepEqual(parseStore('[1, 2]'), {})
  const parsed = parseStore(JSON.stringify({
    commander: { day: '2026-11-15', checkin: null, sleep: true, mood: true, review: 'yes' }, // flags without a check-in
    flight_engineer_1: { day: 'yesterday', checkin: null },
    'bad id!': { day: '2026-11-15', checkin: null },
  }))
  assert.deepEqual(parsed, { commander: { day: '2026-11-15', checkin: null, sleep: false, mood: false, review: false } })
  const proto = parseStore('{"__proto__": {"day": "2026-11-15", "checkin": null}}')
  assert.equal(Object.keys(proto).length, 0)
  assert.equal(Object.getPrototypeOf(proto), Object.prototype) // the saved value cannot replace the prototype
  assert.equal(recordFor(proto, 'toString', '2026-11-15').checkin, null) // inherited names are not records
})
