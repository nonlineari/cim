<?php
declare(strict_types=1);
require __DIR__ . '/includes/hub.php';

hub_render_head('Git Review — CIM Serve Hub');
hub_wrap_open();
hub_render_nav('git-review', true);
?>
    <h1>Git Review <span class="badge">LOCAL ONLY</span></h1>
    <p class="sub">Review via <a href="/index.php">index.php</a> until you approve private GitHub push</p>

    <h2>Local commands</h2>
    <pre>cd /home/s9/Downloads/CIM
git status
git log --oneline -10
git tag -l

cd 06_nls_refs/nls-video-monitor
./serve-cim.sh
# http://127.0.0.1:8765/index.php</pre>

    <h2>GitHub private push (when approved)</h2>
    <div class="panel">
      <p><strong>Placeholder remote:</strong></p>
      <pre>git@github.com:YOUR_ORG/cim-private.git</pre>
      <ol>
        <li>Create a <strong>private</strong> repository on GitHub</li>
        <li><code>git remote add origin git@github.com:YOUR_ORG/cim-private.git</code></li>
        <li><code>git push -u origin main --tags</code></li>
      </ol>
      <p class="sub" style="color:var(--warn);">Do not push until you explicitly approve. Serve Hub PHP is the staging layer.</p>
    </div>

    <h2>Pre-push checklist</h2>
    <ul class="todo" style="list-style:none;padding:0;">
      <li>☐ Open <a href="/index.php">index.php</a> — git meta current (live via PHP)</li>
      <li>☐ <a href="/licenses.php">licenses.php</a> — URW Helvetica row + CIM file links work</li>
      <li>☐ <a href="/cim-approved-plan.php">cim-approved-plan.php</a> — APPROVED badge</li>
      <li>☐ <code>04_rand_blockcode/build.sh</code> passes</li>
      <li>☐ Tags v1.0.0 … v1.0.4 on main</li>
    </ul>
<?php
hub_render_foot();