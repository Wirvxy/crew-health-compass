// Tests for the "Plan for today" day rule and the plan answer check, run with Node's test runner: npm test
// (The plan's progress rules run on the backend and are tested in api/tests/test_personal.py.)
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { msUntilNextUtcDay, utcDay } from '../src/services/dailyPlan.ts'

test('the mission day changes at 00:00 UTC, whatever the local time zone', () => {
  assert.equal(utcDay(Date.parse('2026-11-15T23:59:59.999Z')), '2026-11-15')
  assert.equal(utcDay(Date.parse('2026-11-16T00:00:00.000Z')), '2026-11-16')
  assert.equal(utcDay(Date.parse('2026-11-16T01:30:00+02:00')), '2026-11-15') // 23:30 UTC
})

test('the next reset is at the coming 00:00 UTC', () => {
  assert.equal(msUntilNextUtcDay(Date.parse('2026-11-15T23:59:00Z')), 60_000)
  assert.equal(msUntilNextUtcDay(Date.parse('2026-12-31T00:00:00Z')), 24 * 3_600_000)
  assert.equal(msUntilNextUtcDay(Date.parse('2028-02-28T12:00:00Z')), 12 * 3_600_000) // leap year: Feb 29 follows
})
