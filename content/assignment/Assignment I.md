# Assignment I

**Submission date:** Thursday, May 14, 2026

Submit via Google Forms:

<https://forms.gle/6gPYANzJiyVehsuM7>

(Alternatively, send an email or PDF with the same information.)

- participation voluntary, but you cannot score extra points without participation

---

In the first assignment, each student submits one prediction task. The target can be an event or a real-valued variable. The target must be **unknown on June 4** and **resolve before July 15**.

## Potential Criteria

- **Creativity** — should not be an example from the lecture
- **Relevance** - nice to have, but not obligatory
- **Form** — no spelling mistakes, clear writing
- **Clear resolution** — the outcome must be unambiguously determinable

### Formal requirements

| Field | Requirement |
|---|---|
| Target | Event or real-valued variable |
| Prediction | Probability (for events) or point prediction (for real-valued) |
| Evaluation score | Valid formula with **positive orientation** (higher = better prediction) |

---

## Assignment II

The prediction targets from Assignment I will be shared with the class. In Assignment II (submission deadline **June 4, 2026**), each student submits predictions for all targets.

Each student receives an average score across predictions. Scores for each question are standardized (zero mean, unit variance) so that all questions contribute equally to the overall grade, regardless of their natural scale.

---

## Example 1: Real-valued target

**Prediction question** (should be short):

How many students will be in the class on June 17, 2026?

**Exact resolution criteria** (should be clear, and resolve before July 15, 2026):

The number of people in the room at 9:00h on June 17, 2026, excluding the lecturer. If there is no class, the number is zero.

**Background information** (any potentially relevant information):

Average attendance so far is about 30, but declining.

**Type of target y:**

real-valued

**Type of prediction:**

point prediction for real

**Evaluation score** (formula of target y and prediction p, positive orientation):

$$s(y,p) = 100 - |y-p|$$

---

## Example 2: Event target

**Prediction question** (should be short):

Will there be more than 15 students in the class on June 17, 2026?

**Exact resolution criteria** (should be clear, and resolve before July 15, 2026):

True if at least 16 students are in the room at 9:00h on June 17, 2026, excluding the lecturer. If there is no class, the event is false.

**Background information** (any potentially relevant information):

Average attendance so far is about 30, but declining. Out of experience, attendance tends to increase closer to the exam.

**Type of target y:**

event

**Type of prediction:**

probability for event

**Evaluation score** (formula of target y and prediction p, positive orientation):

$$s(y,p) = 1-(y-p)^2$$
