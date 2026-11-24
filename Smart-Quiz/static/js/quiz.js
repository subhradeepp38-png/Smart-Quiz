/* Smart Quiz — quiz engine (runs on the quiz page) */
(function () {
  "use strict";

  let questions = [];
  let current = 0;
  let answers = {};          // { questionId: 'a'|'b'|'c'|'d' }
  let timeLeft = 0;          // seconds remaining for whole quiz
  let timerId = null;
  let submitted = false;

  const qNumEl = document.getElementById("qNum");
  const qTotalEl = document.getElementById("qTotal");
  const qTextEl = document.getElementById("questionText");
  const optionsBox = document.getElementById("optionsBox");
  const prevBtn = document.getElementById("prevBtn");
  const nextBtn = document.getElementById("nextBtn");
  const submitBtn = document.getElementById("submitBtn");
  const progressBar = document.getElementById("progressBar");
  const answeredCount = document.getElementById("answeredCount");
  const timeLeftEl = document.getElementById("timeLeft");

  const OPTION_LABELS = { a: "A", b: "B", c: "C", d: "D" };

  // ---------- data loading ----------
  async function loadQuiz() {
    try {
      const res = await fetch(API_URL);
      const data = await res.json();
      questions = data.questions;
      timeLeft = questions.length * data.time_per_question;
      qTotalEl.textContent = questions.length;
      startTimer();
      renderQuestion();
    } catch (err) {
      qTextEl.textContent = "Failed to load questions. Please refresh.";
      console.error(err);
    }
  }

  // ---------- timer ----------
  function startTimer() {
    updateTimerDisplay();
    timerId = setInterval(() => {
      timeLeft--;
      updateTimerDisplay();
      if (timeLeft <= 0) {
        clearInterval(timerId);
        submitQuiz(true);
      }
    }, 1000);
  }

  function updateTimerDisplay() {
    const m = Math.floor(timeLeft / 60);
    const s = timeLeft % 60;
    timeLeftEl.textContent = `${m}:${String(s).padStart(2, "0")}`;
    timeLeftEl.parentElement.classList.toggle("text-danger", timeLeft < 60);
  }

  // ---------- rendering ----------
  function renderQuestion() {
    const q = questions[current];
    qNumEl.textContent = current + 1;
    qTextEl.textContent = q.question;
    optionsBox.innerHTML = "";

    Object.entries(q.options).forEach(([key, text]) => {
      const btn = document.createElement("button");
      btn.className = "btn option-btn" + (answers[q.id] === key ? " selected" : "");
      btn.innerHTML = `<span class="opt-key">${OPTION_LABELS[key]}</span>${escapeHtml(text)}`;
      btn.addEventListener("click", () => {
        answers[q.id] = key;
        // re-render to reflect selection styling
        renderQuestion();
        updateProgress();
      });
      optionsBox.appendChild(btn);
    });

    prevBtn.disabled = current === 0;
    nextBtn.innerHTML = current === questions.length - 1
      ? 'Finish <i class="bi bi-check-lg"></i>'
      : 'Next <i class="bi bi-arrow-right"></i>';
    progressBar.style.width = `${((current + 1) / questions.length) * 100}%`;
  }

  function updateProgress() {
    const answered = Object.keys(answers).filter(k => answers[k]).length;
    answeredCount.textContent = `${answered} answered`;
    progressBar.style.width = `${(answered / questions.length) * 100}%`;
  }

  function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, c => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));
  }

  // ---------- navigation ----------
  prevBtn.addEventListener("click", () => {
    if (current > 0) { current--; renderQuestion(); }
  });

  nextBtn.addEventListener("click", () => {
    if (current < questions.length - 1) {
      current++;
      renderQuestion();
    } else {
      submitQuiz(false);
    }
  });

  submitBtn.addEventListener("click", () => submitQuiz(false));

  // ---------- submit ----------
  async function submitQuiz(autoTimeout) {
    if (submitted) return;
    const unanswered = questions.filter(q => !answers[q.id]).length;
    if (!autoTimeout && unanswered > 0) {
      const ok = confirm(`${unanswered} question(s) unanswered. Submit anyway?`);
      if (!ok) return;
    }
    submitted = true;
    clearInterval(timerId);
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Scoring...';

    try {
      const res = await fetch(SUBMIT_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category_id: CATEGORY_ID, answers })
      });
      const data = await res.json();
      window.location.href = RESULT_URL + data.result_id;
    } catch (err) {
      alert("Failed to submit quiz. Please try again.");
      submitted = false;
      submitBtn.disabled = false;
      submitBtn.textContent = "Submit Quiz";
      console.error(err);
    }
  }

  loadQuiz();
})();
