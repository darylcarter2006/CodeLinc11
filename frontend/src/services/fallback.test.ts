import { describe, expect, it } from 'vitest'
import { EXAMPLE } from '../domain/profile'
import { fallbackAnswer } from './fallback'

// Each suggested question on the Chat tab should get its matching standard answer.
describe('standard answers for the suggested questions', () => {
  it.each([
    ['What happens to my $156K work coverage if I change jobs?', 'Coverage through work usually ends when you leave the job.'],
    ['How does $176K compare with the estimate?', "The estimate's starting point for added coverage is $1,425,000."],
    ['Term or whole life for me?', 'many people look at term first. A licensed professional can help you weigh both.'],
    ['How would two policies compare?', 'Laddering means buying two policies'],
    ['What changes if I count my savings?', 'Counting savings lowers the coverage you need'],
  ])('%s', (question, expected) => {
    expect(fallbackAnswer(question, EXAMPLE)).toContain(expected)
  })
})
