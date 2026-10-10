"""Fit offset intervals to a constant drift rate without assuming Gaussian errors."""
import math
import statistics

PPM_PER_STEP = 1.0172526


def fit_offsets(samples, current_trim_steps=0):
    """Samples are (elapsed hours, [offset low, offset high] seconds).

    Find all slopes admitting a single intercept inside every reading's bounds.
    Choose the midpoint least-squares slope/intercept when feasible; otherwise
    project them into the feasible set. Bounds are deterministic, not a CI.
    """
    points = sorted((h * 3600, bounds[0], bounds[1]) for h, bounds in samples)
    assert all(math.isfinite(v) for p in points for v in p)
    assert all(lo <= hi for _, lo, hi in points)
    if len(points) < 2 or points[0][0] == points[-1][0]:
        return dict(available=False, reason='At least two distinct observation times required')
    lower, upper = -math.inf, math.inf
    for i, (x, lo, hi) in enumerate(points):
        for xx, ll, hh in points[i + 1:]:
            if xx == x:
                if max(lo, ll) > min(hi, hh):
                    return dict(available=False, reason='Same-time measurement bounds conflict')
                continue
            lower = max(lower, (ll - hi) / (xx - x))
            upper = min(upper, (hh - lo) / (xx - x))
    if lower > upper + 1e-12:
        return dict(available=False, reason='No constant-rate line satisfies every measurement interval',
                    pairwise_slope_limits_ppm=[lower * 1e6, upper * 1e6])
    if lower > upper:
        # Floating-point crossings of an exact line can differ by a few ulps.
        lower = upper = (lower + upper) / 2
    xs = [p[0] for p in points]
    ys = [(p[1] + p[2]) / 2 for p in points]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    ols = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    slope = min(upper, max(lower, ols))

    def intercept_bounds(b):
        return max(lo - b*x for x, lo, _ in points), min(hi - b*x for x, _, hi in points)

    alo, ahi = intercept_bounds(slope)
    intercept = min(ahi, max(alo, my - slope * mx))
    # Vertices of the feasible slope/intercept polygon determine all linear
    # prediction extrema. Include pairwise crossings of both bound envelopes.
    slopes = {lower, upper}
    for i, (x, lo, hi) in enumerate(points):
        for xx, ll, hh in points[i + 1:]:
            if xx == x:
                continue
            for y in (lo, hi):
                for yy in (ll, hh):
                    b = (yy - y) / (xx - x)
                    if lower <= b <= upper:
                        slopes.add(b)
    vertices = []
    for b in slopes:
        low, high = intercept_bounds(b)
        if low <= high + 1e-10:
            vertices.extend([(b, low), (b, high)])

    def envelope(x):
        values = [a + b*x for b, a in vertices]
        return [min(values), max(values)]

    residuals = [dict(elapsed_hours=x/3600, offset_midpoint_s=y,
                      fitted_offset_s=intercept+slope*x, residual_s=y-intercept-slope*x,
                      residual_interval_s=[lo-intercept-slope*x, hi-intercept-slope*x])
                 for (x, lo, hi), y in zip(points, ys)]
    rs = [r['residual_s'] for r in residuals]
    ppm = slope * 1e6
    adjustment = round(-ppm / PPM_PER_STEP)
    trim = current_trim_steps + adjustment
    residual_ppm = [lower*1e6 + adjustment*PPM_PER_STEP, upper*1e6 + adjustment*PPM_PER_STEP]
    predictions = []
    for hours in (24, 168, 720):
        seconds = hours * 3600
        correction = adjustment * PPM_PER_STEP * seconds / 1e6
        total = [v + correction for v in envelope(xs[-1] + seconds)]
        predictions.append(dict(horizon_hours=hours,
            additional_error_seconds=(ppm + adjustment*PPM_PER_STEP) * seconds/1e6,
            additional_error_interval_s=[v * seconds/1e6 for v in residual_ppm],
            total_utc_offset_interval_s=total))
    return dict(available=True, sample_count=len(points), elapsed_hours=xs[-1]/3600,
        slope_ppm=ppm, slope_interval_ppm=[lower*1e6, upper*1e6],
        slope_uncertainty_minus_ppm=ppm-lower*1e6, slope_uncertainty_plus_ppm=upper*1e6-ppm,
        ols_midpoint_slope_ppm=ols*1e6, intercept_seconds=intercept,
        intercept_interval_seconds=envelope(0),
        fitted_points=[dict(elapsed_hours=x/3600, fitted_offset_s=intercept+slope*x,
                            fitted_offset_interval_s=envelope(x)) for x in xs],
        residuals=residuals, residual_rmse_seconds=math.sqrt(statistics.mean(v*v for v in rs)),
        residual_sample_std_seconds=statistics.stdev(rs) if len(rs)>1 else None,
        max_absolute_residual_seconds=max(abs(v) for v in rs),
        current_trim_steps=current_trim_steps, recommended_trim_steps=trim, trim_adjustment_steps=adjustment,
        correction_steps_interval=[current_trim_steps + round(-upper*1e6/PPM_PER_STEP), current_trim_steps + round(-lower*1e6/PPM_PER_STEP)],
        predicted_residual_ppm_interval=residual_ppm, predictions_after_trim=predictions,
        method='Constant-rate line through absolute UTC offset intervals, with free intercept. '
               'Unweighted least squares of interval midpoints projected into the feasible set. '
               'Slope and prediction bounds span every line compatible with all measurement bounds; not statistical confidence intervals.',
        prediction_assumption='Hypothetical recommended trim applied at latest observation; UTC not reset. '
                              'Rate and temperature conditions remain constant. Residuals are descriptive, not clock jitter.')
