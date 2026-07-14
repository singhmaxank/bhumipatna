{% extends 'base.html' %}
{% block title %}Bhumi Patna Portal - Intern Dashboard{% endblock %}

{% block content %}
<div class="bento-grid">
    
    <!-- Graphic Card: Doughnut Chart for Progress -->
    <div class="bento-card span-4" style="align-items: center; justify-content: center; text-align: center;">
        <h3 class="card-title">Tenure Progress</h3>
        <div style="position: relative; width: 140px; height: 140px; margin: 1rem 0;">
            <canvas id="progressChart"></canvas>
            <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-weight: 800; font-size: 1.5rem;">
                {{ progress_percent }}%
            </div>
        </div>
        <p class="subtext">{{ days_left }} Days Remaining</p>
    </div>

    <!-- Info Cards -->
    <div class="bento-card span-4">
        <h3 class="card-title">Total Approved Raised</h3>
        <div class="card-value" style="color: var(--primary);">₹{{ total_donated }}</div>
        <div style="margin-top: auto;">
            <p class="subtext">Reporting Head:</p>
            <p style="font-weight: 700;">{{ head_name }}</p>
        </div>
    </div>

    <!-- Dark Accent Card: Fast Log -->
    <div class="bento-card span-4 card-dark">
        <h3 class="card-title" style="color: rgba(255,255,255,0.7);">Quick Action</h3>
        <div class="card-value" style="font-size: 1.5rem;">Log Collection</div>
        <p class="subtext" style="color: rgba(255,255,255,0.7); margin-bottom: 1.5rem;">Record a new donor entry.</p>
        <a href="#logForm" class="btn" style="background: #ffffff; color: var(--primary-dark); width: 100%;">Add New +</a>
    </div>

    <!-- Log Donation Form -->
    <div class="bento-card span-6" id="logForm">
        <h3 class="card-title">Donor Submission Form</h3>
        <form action="/submit-donation" method="POST">
            <div class="form-group">
                <label>Donor Full Name</label>
                <input type="text" name="donor_name" placeholder="e.g. Rahul Kumar" required>
            </div>
            <div class="form-group">
                <label>Donor Phone Number</label>
                <input type="text" name="donor_phone" placeholder="10-digit mobile number" required>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                <div class="form-group">
                    <label>Amount (₹)</label>
                    <input type="number" name="amount" required>
                </div>
                <div class="form-group">
                    <label>UTR / Transaction ID</label>
                    <input type="text" name="utr" required>
                </div>
            </div>
            <div class="form-group">
                <label>Drive Screenshot Link (Optional)</label>
                <input type="url" name="screenshot_url" placeholder="https://drive.google.com/file/d/...">
            </div>
            <button type="submit" class="btn" style="width: 100%; margin-top: 0.5rem;"><i class="ph ph-paper-plane-tilt" style="margin-right: 8px;"></i> Submit for Verification</button>
        </form>
    </div>

    <!-- My Collections Table -->
    <div class="bento-card span-6">
        <h3 class="card-title">My Collection History</h3>
        <div class="table-wrapper">
            <table class="data-table">
                <thead>
                    <tr>
                        <th style="width: 45%;">Donor Name</th>
                        <th style="width: 25%;">Amount</th>
                        <th style="width: 30%; text-align: right;">Status</th>
                    </tr>
                </thead>
                <tbody>
                    {% for d in my_donations %}
                    <tr>
                        <td><strong>{{ d.donor_name }}</strong></td>
                        <td><strong style="color: var(--primary);">₹{{ d.amount }}</strong></td>
                        <td style="text-align: right;">
                            <span class="badge badge-{{ d.status }}">{{ d.status }}</span>
                        </td>
                    </tr>
                    {% else %}
                    <tr><td colspan="3" style="text-align: center; color: var(--text-muted); padding: 2rem 0;">No donations logged yet.</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>

<!-- Doughnut Chart Script -->
<script>
    document.addEventListener("DOMContentLoaded", function() {
        const ctx = document.getElementById('progressChart').getContext('2d');
        const progress = {{ progress_percent }};
        const remaining = 100 - progress;
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';

        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Completed', 'Remaining'],
                datasets: [{
                    data: [progress, remaining],
                    backgroundColor: ['#059669', isDark ? '#334155' : '#e2e8f0'],
                    borderWidth: 0,
                    cutout: '75%', // Makes the ring thin and modern
                    borderRadius: 20
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { enabled: false } },
                animation: { animateScale: true, animateRotate: true }
            }
        });
    });
</script>
{% endblock %}