<?php
declare(strict_types=1);
require __DIR__ . '/includes/hub.php';

hub_render_head('Licenses — CIM Serve Hub');
hub_wrap_open();
hub_render_nav('licenses', true);
?>
    <h1>CIM License Matrix <span class="badge">NLS Records</span></h1>
    <p class="sub">NLS Visualist · A. Visualist · Helvetica — quad + typography layers</p>

    <table>
      <thead><tr><th>Layer</th><th>License</th><th>Scope</th><th>File</th></tr></thead>
      <tbody>
        <tr>
          <td><strong>Software</strong></td>
          <td>MIT</td>
          <td>RAND BlockCode Java, Python generators, build scripts</td>
          <td><a href="<?= cim_href('LICENSE') ?>">LICENSE</a></td>
        </tr>
        <tr>
          <td><strong>Disinformation Architecture</strong></td>
          <td>CIM v1.0</td>
          <td>Tutorials, .diff docs, notation, manifests, Serve Hub HTML</td>
          <td><a href="<?= cim_href('LICENSE-CIM') ?>">LICENSE-CIM</a></td>
        </tr>
        <tr>
          <td><strong>Experiments</strong></td>
          <td>WTFPL v2</td>
          <td>Processing sketches, OCR dumps, NLS experimental refs</td>
          <td><a href="<?= cim_href('LICENSE-WTFPL') ?>">LICENSE-WTFPL</a></td>
        </tr>
        <tr>
          <td><strong>Future brand fonts</strong></td>
          <td>OFL-1.1</td>
          <td>OFL-marked <code>.ttf</code> / <code>.otf</code> in <code>fonts/</code></td>
          <td><a href="<?= cim_href('LICENSE-OFL') ?>">LICENSE-OFL</a></td>
        </tr>
        <tr>
          <td><strong>Helvetica (A. Visualist)</strong></td>
          <td>URW Base 35</td>
          <td>NimbusSans archive, ReportLab Standard 14 names, PDF exports</td>
          <td><a href="<?= cim_href('LICENSE-TYPOGRAPHY') ?>">LICENSE-TYPOGRAPHY</a> · <a href="<?= cim_href('fonts/CIM-Visualist/Helvetica/NimbusSans/LICENSE-URW.txt') ?>">URW</a></td>
        </tr>
      </tbody>
    </table>

    <h2>Summaries</h2>
    <ul>
      <li><a href="<?= cim_href('07_conversation_entity/CIM-LICENSE.md') ?>">CIM-LICENSE.md</a></li>
      <li><a href="<?= cim_href('07_conversation_entity/WTFPL-SCOPE.md') ?>">WTFPL-SCOPE.md</a></li>
      <li><a href="<?= cim_href('07_conversation_entity/OFL-SCOPE.md') ?>">OFL-SCOPE.md</a></li>
      <li><a href="<?= cim_href('07_conversation_entity/URW-SCOPE.md') ?>">URW-SCOPE.md</a></li>
      <li><a href="<?= cim_href('fonts/CIM-Visualist/A-VISUALIST.md') ?>">A-VISUALIST.md</a> — Helvetica canon</li>
    </ul>

    <blockquote>
      PDF credit line: <code>NLS Visualist · A. Visualist · Helvetica — CIM / NLS Records</code><br>
      Architecture credit: <code>Disinformation Architecture — CIM / NLS Records</code>
    </blockquote>
<?php
hub_render_foot();