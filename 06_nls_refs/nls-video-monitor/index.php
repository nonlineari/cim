<?php
declare(strict_types=1);
require __DIR__ . '/includes/hub.php';

hub_render_head('CIM Serve Hub — NLS Records');
hub_wrap_open();
hub_render_nav('index');
?>
    <h1>CIM Serve Hub <span class="badge badge-ok">REQUIRED ENTRY</span></h1>
    <p class="sub">NLS Visualist · A. Visualist · Helvetica — Copyright © 2026 NLS Records</p>
    <p class="sub">Local git review until private GitHub push · <code>RAND System B \ RAND System A | NLS YOLODarket STEM</code></p>

    <?php hub_render_git_meta(); ?>

    <h2>Review pages</h2>
    <div class="cards">
      <div class="card"><a href="/licenses.php">licenses.php</a><p>MIT · CIM · WTFPL · OFL · URW Helvetica</p></div>
      <div class="card"><a href="/changelog.php">changelog.php</a><p>Release history v1.0.0–v1.0.4</p></div>
      <div class="card"><a href="/cim-approved-plan.php">cim-approved-plan.php</a><p>CIM entity APPROVED plan</p></div>
      <div class="card"><a href="/git-review.php">git-review.php</a><p>GitHub private push checklist</p></div>
      <div class="card"><a href="/plan.html">plan.html</a><p>Gravity AVD/POS APPROVED plan</p></div>
      <div class="card"><a href="/gravity_serve.html">gravity_serve.html</a><p>NLS Visualist dashboard</p></div>
    </div>

    <h2>Local serve (PHP)</h2>
    <pre>cd /home/s9/Downloads/CIM/06_nls_refs/nls-video-monitor
./serve-cim.sh
# open http://127.0.0.1:8765/index.php</pre>

    <h2>CIM archive paths</h2>
    <table>
      <thead><tr><th>System</th><th>Path</th></tr></thead>
      <tbody>
        <tr><td>RAND BlockCode Java</td><td><code><?= htmlspecialchars(cim_href('04_rand_blockcode/'), ENT_QUOTES) ?></code></td></tr>
        <tr><td>RAND System A (dual)</td><td><code><?= htmlspecialchars(cim_href('05_extrusion_sketches/Extrusion3_2_2_1_MONO_XXI_PS_INT_dual/'), ENT_QUOTES) ?></code></td></tr>
        <tr><td>RAND System B (dUP)</td><td><code><?= htmlspecialchars(cim_href('05_extrusion_sketches/Extrusion3_2_2_1_MONO_XXI_PS_INT_dUP/'), ENT_QUOTES) ?></code></td></tr>
        <tr><td>Typography</td><td><code><?= htmlspecialchars(cim_href('fonts/CIM-Visualist/'), ENT_QUOTES) ?></code></td></tr>
      </tbody>
    </table>
<?php
hub_render_foot();