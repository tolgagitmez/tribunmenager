'use strict';

(function () {
  const kindLabels = {
    cross: ['Orta', 'Orta açma'],
    corner: ['Korner', 'Korner'],
    'free-kick': ['Serbest vuruş', 'Frikik'],
    penalty: ['Penaltı', 'Penaltı']
  };

  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  const finite = (value, fallback) => Number.isFinite(value) ? value : fallback;
  const signed = (value) => value > 0 ? `+${value}` : String(value);

  class ManagerKickPanel {
    constructor(mount, {onChange, onStrike, onAuto} = {}) {
      this.mount = mount;
      this.onChange = onChange;
      this.onStrike = onStrike;
      this.onAuto = onAuto;
      this.opportunity = null;
      this.stage = 1;
      this.pointerId = null;
      this.submitting = false;
      mount.hidden = true;
      mount.classList.add('manager-kick');
      mount.setAttribute('role', 'region');
      mount.setAttribute('aria-labelledby', 'managerKickTitle');
      mount.innerHTML = `
        <header class="manager-kick-header">
          <div>
            <p class="manager-kick-kind" data-kick-kind></p>
            <h2 tabindex="-1" id="managerKickTitle">Yön ve güç</h2>
          </div>
          <div class="manager-kick-player">
            <strong data-kick-player></strong>
            <span data-kick-skill></span>
          </div>
        </header>
        <ol class="manager-kick-steps" aria-label="Vuruş adımları">
          <li data-kick-step="1">1. Yön ve güç</li>
          <li data-kick-step="2">2. Temas noktası</li>
        </ol>
        <div data-kick-stage="1">
          <p class="manager-kick-instruction">Sahaya dokun veya hedef okunu sürükle. Yönü ve gücü kaydırıcılarla da ayarlayabilirsin.</p>
          <p class="manager-kick-instruction" data-kick-indirect hidden>Gol için vuruştan sonra topa başka bir oyuncunun dokunması gerekir.</p>
          <div class="manager-kick-aim">
            <div class="manager-kick-range">
              <span><label for="managerKick-direction">Yön</label><output aria-hidden="true" data-kick-output="direction"></output></span>
              <input id="managerKick-direction" data-kick-input="direction" type="range" min="-45" max="45" step="1" value="0">
            </div>
            <div class="manager-kick-range">
              <span><label for="managerKick-power">Güç</label><output aria-hidden="true" data-kick-output="power"></output></span>
              <input id="managerKick-power" data-kick-input="power" type="range" min="0" max="100" step="1" value="60">
            </div>
          </div>
        </div>
        <div class="manager-kick-impact" data-kick-stage="2" hidden>
          <button type="button" class="manager-kick-ball" aria-label="Top üzerinde temas noktasını seç"
              aria-describedby="managerKickImpactHelp" data-kick-ball>
            <span aria-hidden="true" class="manager-kick-ball-seams"></span>
            <span aria-hidden="true" class="manager-kick-ball-panels">
              <i></i><i></i><i></i><i></i><i></i><i></i>
            </span>
            <span aria-hidden="true" class="manager-kick-ball-light"></span>
            <span aria-hidden="true" class="manager-kick-ball-marker" data-kick-marker></span>
          </button>
          <div class="manager-kick-impact-controls">
            <p class="manager-kick-instruction" id="managerKickImpactHelp">Topa dokun veya ok tuşlarıyla işareti taşı. Alt temas topu yükseltir, üst temas alçaltır. Yan temas falso verir.</p>
            <div class="manager-kick-range">
              <span><label for="managerKick-contactX">Yatay temas</label><output aria-hidden="true" data-kick-output="contactX"></output></span>
              <input id="managerKick-contactX" data-kick-input="contactX" type="range" min="-100" max="100" step="1" value="0">
            </div>
            <div class="manager-kick-range">
              <span><label for="managerKick-contactY">Dikey temas</label><output aria-hidden="true" data-kick-output="contactY"></output></span>
              <input id="managerKick-contactY" data-kick-input="contactY" type="range" min="-100" max="100" step="1" value="0">
            </div>
          </div>
        </div>
        <footer class="manager-kick-actions">
          <button type="button" data-kick-auto>Oyuncuya bırak</button>
          <button type="button" data-kick-back hidden>Geri</button>
          <button type="button" class="manager-kick-primary" data-kick-next>Temas noktasına geç</button>
          <button type="button" class="manager-kick-primary" data-kick-strike hidden>Vuruşu yap</button>
        </footer>`;

      const find = (selector) => mount.querySelector(selector);
      this.title = find('#managerKickTitle');
      this.kind = find('[data-kick-kind]');
      this.player = find('[data-kick-player]');
      this.skill = find('[data-kick-skill]');
      this.indirectNotice = find('[data-kick-indirect]');
      this.ball = find('[data-kick-ball]');
      this.marker = find('[data-kick-marker]');
      this.input = {};
      this.output = {};
      for (const key of ['direction', 'power', 'contactX', 'contactY']) {
        this.input[key] = find(`[data-kick-input="${key}"]`);
        this.output[key] = find(`[data-kick-output="${key}"]`);
        this.input[key].addEventListener('input', () => this.readRange(key));
      }
      this.stepLabels = [...mount.querySelectorAll('[data-kick-step]')];
      this.stageViews = [...mount.querySelectorAll('[data-kick-stage]')];
      this.next = find('[data-kick-next]');
      this.back = find('[data-kick-back]');
      this.strike = find('[data-kick-strike]');
      this.auto = find('[data-kick-auto]');
      this.next.addEventListener('click', () => this.changeStage(2));
      this.back.addEventListener('click', () => this.changeStage(1));
      this.strike.addEventListener('click', () => this.resolve(this.onStrike));
      this.auto.addEventListener('click', () => this.resolve(this.onAuto));
      this.ball.addEventListener('pointerdown', (event) => this.pressBall(event));
      this.ball.addEventListener('pointermove', (event) => this.moveOnBall(event));
      this.ball.addEventListener('pointerup', (event) => {
        this.moveOnBall(event);
        this.endBallPress(event);
      });
      this.ball.addEventListener('pointercancel', (event) => this.endBallPress(event));
      this.ball.addEventListener('lostpointercapture', (event) => this.endBallPress(event));
      this.ball.addEventListener('keydown', (event) => this.moveContactWithKey(event));
    }

    show(opportunity) {
      if (!opportunity || (this.opportunity && this.opportunity.id === opportunity.id)) return;
      if (!this.opportunity) this.returnFocus = this.mount.ownerDocument.activeElement;
      this.opportunity = opportunity;
      this.directionRange = Math.floor(clamp(finite(opportunity.angleRangeDeg, 45), 0, 180));
      this.input.direction.min = -this.directionRange;
      this.input.direction.max = this.directionRange;
      this.input.direction.disabled = this.directionRange === 0;
      this.value = {
        direction: clamp(finite(opportunity.direction, 0), -this.directionRange, this.directionRange),
        power: clamp(finite(opportunity.power, 60), 0, 100),
        contactX: 0,
        contactY: 0
      };
      const [kind, skillName] = kindLabels[opportunity.kind] || ['Vuruş', 'Vuruş'];
      this.kind.textContent = opportunity.indirect ? 'Endirekt serbest vuruş' : kind;
      this.indirectNotice.hidden = !opportunity.indirect;
      this.player.textContent = opportunity.playerName || 'Oyuncu';
      this.skill.textContent = `${skillName} yeteneği · ${Math.round(clamp(finite(opportunity.skill, 0), 0, 100))} / 100`;
      this.mount.hidden = false;
      this.changeStage(1);
    }

    hide() {
      if (!this.opportunity) return;
      const target = this.returnFocus;
      const restoreFocus = this.mount.contains(this.mount.ownerDocument.activeElement);
      this.mount.hidden = true;
      this.opportunity = null;
      this.returnFocus = null;
      this.pointerId = null;
      if (restoreFocus && target?.isConnected) target.focus({preventScroll: true});
    }

    setAim(direction, power) {
      if (!this.opportunity || this.stage !== 1) return;
      this.value.direction = clamp(finite(direction, this.value.direction), -this.directionRange, this.directionRange);
      this.value.power = clamp(finite(power, this.value.power), 0, 100);
      this.updateValues();
    }

    changeStage(stage) {
      if (!this.opportunity) return;
      this.stage = stage;
      this.title.textContent = stage === 1 ? 'Yön ve güç' : 'Topa nereden vuracaksın?';
      this.stepLabels.forEach((label) => {
        if (Number(label.dataset.kickStep) === stage) label.setAttribute('aria-current', 'step');
        else label.removeAttribute('aria-current');
      });
      this.stageViews.forEach((view) => {
        view.hidden = Number(view.dataset.kickStage) !== stage;
      });
      this.back.hidden = stage === 1;
      this.strike.hidden = stage === 1;
      this.next.hidden = stage === 2;
      this.updateValues();
      this.title.focus({preventScroll: true});
    }

    readRange(key) {
      if (!this.opportunity) return;
      const value = this.input[key].valueAsNumber;
      if (key === 'direction' || key === 'power') {
        if (key === 'direction') this.setAim(value);
        else this.setAim(undefined, value);
        return;
      }
      this.setContactAxis(key, value / 100);
    }

    setContactAxis(key, value) {
      if (!this.opportunity || this.stage !== 2) return;
      const other = key === 'contactX' ? this.value.contactY : this.value.contactX;
      const limit = Math.sqrt(Math.max(0, 1 - other * other));
      this.value[key] = clamp(value, -limit, limit);
      this.updateValues();
    }

    pressBall(event) {
      if (!this.opportunity || this.stage !== 2 || this.pointerId !== null || event.button !== 0) return;
      this.pointerId = event.pointerId;
      this.ball.setPointerCapture(event.pointerId);
      this.moveOnBall(event);
    }

    moveOnBall(event) {
      if (!this.opportunity || this.stage !== 2 || event.pointerId !== this.pointerId) return;
      const rect = this.ball.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return;
      const x = 2 * (event.clientX - rect.left) / rect.width - 1;
      const y = 1 - 2 * (event.clientY - rect.top) / rect.height;
      const magnitude = Math.max(1, Math.hypot(x, y));
      this.value.contactX = x / magnitude;
      this.value.contactY = y / magnitude;
      this.updateValues();
    }

    endBallPress(event) {
      if (event.pointerId === this.pointerId) this.pointerId = null;
    }

    moveContactWithKey(event) {
      const step = event.shiftKey ? 0.20 : 0.05;
      const arrows = {
        ArrowLeft: ['contactX', -step],
        ArrowRight: ['contactX', step],
        ArrowUp: ['contactY', step],
        ArrowDown: ['contactY', -step]
      };
      const move = arrows[event.key];
      if (!move) return;
      event.preventDefault();
      const [key, amount] = move;
      this.setContactAxis(key, this.value[key] + amount);
    }

    updateValues() {
      const {direction, power, contactX, contactY} = this.value;
      const readouts = {
        direction: `${signed(Math.round(direction))}°`,
        power: `%${Math.round(power)}`,
        contactX: contactLabel(contactX, 'Sol', 'Sağ'),
        contactY: contactLabel(contactY, 'Alt', 'Üst')
      };
      this.input.direction.value = Math.round(direction);
      this.input.power.value = Math.round(power);
      this.input.contactX.value = Math.round(contactX * 100);
      this.input.contactY.value = Math.round(contactY * 100);
      for (const [key, label] of Object.entries(readouts)) {
        this.output[key].value = label;
        this.input[key].setAttribute('aria-valuetext', label);
      }
      this.marker.style.left = `${(1 + contactX) * 50}%`;
      this.marker.style.top = `${(1 - contactY) * 50}%`;
      this.ball.setAttribute('aria-label', `Top üzerinde temas noktası, yatay ${readouts.contactX}, dikey ${readouts.contactY}`);
      this.onChange?.(this.opportunity, {...this.value}, this.stage);
    }

    resolve(callback) {
      if (!this.opportunity || this.submitting) return;
      this.submitting = true;
      try {
        callback?.(this.opportunity, {...this.value});
      } finally {
        this.submitting = false;
      }
    }
  }

  function contactLabel(value, negative, positive) {
    const percent = Math.round(Math.abs(value) * 100);
    return percent === 0 ? 'Merkez' : `${value < 0 ? negative : positive} %${percent}`;
  }

  window.TribunManagerKickPanel = ManagerKickPanel;
})();
