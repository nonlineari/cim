<?php
declare(strict_types=1);
require __DIR__ . '/includes/hub.php';

$version = hub_version();
hub_render_head('Changelog — CIM Serve Hub');
hub_wrap_open();
hub_render_nav('changelog', true);
?>
    <h1>CHANGELOG <span class="badge badge-ok">v<?= htmlspecialchars($version, ENT_QUOTES) ?></span></h1>
    <p class="sub">Copyright © 2026 NLS Records · <a href="<?= cim_href('CHANGELOG.md') ?>">CHANGELOG.md</a></p>

    <h2>[1.0.4] — 2026-07-07</h2>
    <h3>Added</h3>
    <ul>
      <li><strong>index.php</strong> — PHP Serve Hub with shared nav + live git meta</li>
      <li>licenses.php, changelog.php, cim-approved-plan.php, git-review.php</li>
      <li>router.php, serve-cim.sh — CIM archive file serving</li>
      <li>LICENSE-TYPOGRAPHY, URW-SCOPE.md — Helvetica in license matrix</li>
    </ul>
    <h3>Changed</h3>
    <ul>
      <li>plan.html nav links to PHP hub</li>
      <li>CIM-LICENSE.md — URW Helvetica separate from OFL</li>
    </ul>

    <h2>[1.0.3] — 2026-07-07</h2>
    <ul>
      <li>Helvetica canon — A-VISUALIST.md, NimbusSans archive, cim_visualist_typography.py</li>
      <li>Tutorial PDF — Visualist header/footer</li>
    </ul>

    <h2>[1.0.2] — 2026-07-07</h2>
    <ul>
      <li>CHANGELOG.md, LICENSE-OFL, fonts/ layer</li>
    </ul>

    <h2>[1.0.1] — 2026-07-07</h2>
    <ul>
      <li>LICENSE-CIM (Disinformation Architecture), LICENSE-WTFPL</li>
    </ul>

    <h2>[1.0.0] — 2026-07-07</h2>
    <ul>
      <li>Initial CIM Generation 1 — RAND BlockCode Java, tutorials, Extrusion sketches</li>
      <li>MIT License — © NLS Records</li>
    </ul>
<?php
hub_render_foot();