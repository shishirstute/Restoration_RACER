import math

class CLPULoadCalculator:
    """
    Net-load output:
      {'Bus': str, 'P1': kW, 'Q1': 0, 'P2': kW, 'Q2': 0, 'P3': kW, 'Q3': 0}

    • Outage           → forecast + PV + CLPU_peak
    • First step back  → forecast + CLPU_peak                (PV still offline)
    • Decay window     → forecast + CLPU_peak· e^(−3·t/T)    (PV excluded)
    • After tail dies  → forecast                            (PV excluded)

      T  (minutes of decay)  is proportional to outage length
      via  k_duration · Temp_amb · outage_hours  (same formula as IEEE papers).
    """
    def __init__(
        self,
        N_hvac: int = 6,
        P_rated: float = 0.9, # change this to 0.9 by shishir
        diversity_factor: float = 0.6,
        k_norm: float = 0.8,
        k_duration: float = 0.01,
        Temp_amb: float = 28,
        interval_minutes: int = 15,
        growth_per_step: float = 0.1, # changed to 0.1 by shishir
    ):
        self.N_hvac, self.P_rated = N_hvac, P_rated
        self.diversity_factor, self.k_norm = diversity_factor, k_norm
        self.k_duration, self.Temp_amb = k_duration, Temp_amb
        self.interval_minutes, self.growth_per_step = interval_minutes, growth_per_step

        # internal counters
        self.t = 0
        self.prev_status = 0
        self.outage_steps = 0
        self.clpu_peak = 0.0
        self.decay_steps = 0
        self.decay_elapsed = 0
        self.first_after_rest = False

    # ---------------------------------------------------------------------
    def _status(self, t_out: int, t_rest: int) -> int:
        if t_out == 0 or t_rest == 0:
            return 1 if (t_out > 0 and self.t >= t_out) else 0
        return 1 if t_out <= self.t <= t_rest else 0

    def _compute_clpu_peak(self, steps_in_outage: int) -> float:
        hvac_block = self.N_hvac * self.P_rated * self.diversity_factor * self.k_norm
        return hvac_block * (1 + self.growth_per_step * max(steps_in_outage - 1, 0))

    # ---------------------------------------------------------------------
    def step(
        self,
        forecast_dict: dict,
        pv_dict: dict,
        outage_start: int,
        restoration_end: int
    ) -> dict:

        status = self._status(outage_start, restoration_end)

        # unpack inputs
        bus = forecast_dict["Bus"]
        fp1, fp2, fp3 = forecast_dict["P1"], forecast_dict["P2"], forecast_dict["P3"]
        pv1, pv2, pv3 = pv_dict.get("P1", 0.0), pv_dict.get("P2", 0.0), pv_dict.get("P3", 0.0)

        # -------- outage bookkeeping --------------------------------------
        if status == 1:                          # still de-energised
            self.outage_steps += 1
            self.clpu_peak = self._compute_clpu_peak(self.outage_steps)

        if status == 0 and self.prev_status == 1:   # restoration moment
            self.first_after_rest = True
            # tail duration proportional to outage hours
            T_out_h = (self.outage_steps * self.interval_minutes) / 60
            decay_minutes = math.ceil(self.k_duration * self.Temp_amb * T_out_h * 60)
            self.decay_steps = max(1, decay_minutes // self.interval_minutes)
            self.decay_elapsed = 0
            self.outage_steps = 0

        # -------- choose scenario -----------------------------------------
        if status == 1:                              # outage interval
            surge = self.clpu_peak
            pv_factor = +1                           # add PV

        elif self.first_after_rest:                  # first 15-min post-restore
            surge = self.clpu_peak
            pv_factor = 0
            self.first_after_rest = False
            self.decay_elapsed += 1                  # start the timer

        elif 0 < self.decay_elapsed < self.decay_steps:
            decay = math.exp(-3 * self.decay_elapsed / self.decay_steps)
            surge = self.clpu_peak * decay
            pv_factor = -1
            self.decay_elapsed += 1

        else:                                        # tail finished or normal
            surge = 0.0
            pv_factor = -1 if self.decay_steps > 0 else 0

        surge_per_phase = surge / 3.0

        net_p1 = fp1 + pv_factor * pv1 + surge_per_phase
        net_p2 = fp2 + pv_factor * pv2 + surge_per_phase
        net_p3 = fp3 + pv_factor * pv3 + surge_per_phase

        self.prev_status = status
        self.t += 1

        return {
            "Bus": bus,
            "P1": net_p1, "Q1": 0,
            "P2": net_p2, "Q2": 0,
            "P3": net_p3, "Q3": 0,
        }
