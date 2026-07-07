<?php
declare(strict_types=1);

/** CIM Serve Hub — shared bootstrap, nav, git meta, CIM asset paths. */

const HUB_DIR = __DIR__ . '/..';
const CIM_ROOT = HUB_DIR . '/../..';

function hub_cim_root(): string
{
    return realpath(CIM_ROOT) ?: CIM_ROOT;
}

/** URL path to a file under CIM root (served by router.php). */
function cim_href(string $rel): string
{
    return '/' . ltrim(str_replace('\\', '/', $rel), '/');
}

function hub_version(): string
{
    $file = hub_cim_root() . '/VERSION';
    return is_file($file) ? trim((string) file_get_contents($file)) : '?';
}

function hub_git(string ...$args): string
{
    $cmd = array_merge(['git', '-C', hub_cim_root()], $args);
    $out = [];
    $code = 0;
    exec(implode(' ', array_map('escapeshellarg', $cmd)), $out, $code);
    return $code === 0 ? trim(implode("\n", $out)) : '';
}

function hub_git_meta(): array
{
    return [
        'branch' => hub_git('branch', '--show-current') ?: 'main',
        'dirty' => hub_git('status', '--porcelain') !== '' ? 'dirty' : 'clean',
        'version' => hub_version(),
        'commit' => hub_git('log', '-1', '--format=%h %s') ?: 'n/a',
        'tags' => str_replace("\n", ', ', hub_git('tag', '-l') ?: '(none)'),
    ];
}

function hub_nav_items(): array
{
    return [
        'index' => ['href' => '/index.php', 'label' => 'index.php', 'strong' => true],
        'plan' => ['href' => '/plan.html', 'label' => 'Gravity Plan'],
        'cim-plan' => ['href' => '/cim-approved-plan.php', 'label' => 'CIM Plan'],
        'licenses' => ['href' => '/licenses.php', 'label' => 'Licenses'],
        'changelog' => ['href' => '/changelog.php', 'label' => 'Changelog'],
        'git-review' => ['href' => '/git-review.php', 'label' => 'Git Review'],
        'gravity' => ['href' => '/gravity_serve.html', 'label' => 'Visualist'],
    ];
}

function hub_render_nav(string $active = 'index', bool $backLink = false): void
{
    $items = hub_nav_items();
    echo '<div class="nav">';
    if ($backLink && $active !== 'index') {
        echo '<a href="/index.php">← CIM Serve Hub</a>';
    }
    foreach ($items as $key => $item) {
        if ($backLink && $key === 'index') {
            continue;
        }
        $class = $key === $active ? ' class="active"' : '';
        $label = htmlspecialchars($item['label'], ENT_QUOTES, 'UTF-8');
        $href = htmlspecialchars($item['href'], ENT_QUOTES, 'UTF-8');
        if (!empty($item['strong']) && !$backLink) {
            echo "<a href=\"{$href}\"{$class}><strong>{$label}</strong></a>";
        } else {
            echo "<a href=\"{$href}\"{$class}>{$label}</a>";
        }
    }
    echo '</div>';
}

function hub_render_head(string $title): void
{
    $safe = htmlspecialchars($title, ENT_QUOTES, 'UTF-8');
    echo <<<HTML
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{$safe}</title>
  <link rel="stylesheet" href="/serve-hub-common.css">
</head>
<body>
HTML;
}

function hub_render_git_meta(): void
{
    $m = hub_git_meta();
    $branch = htmlspecialchars($m['branch'], ENT_QUOTES, 'UTF-8');
    $dirty = htmlspecialchars($m['dirty'], ENT_QUOTES, 'UTF-8');
    $version = htmlspecialchars($m['version'], ENT_QUOTES, 'UTF-8');
    $commit = htmlspecialchars($m['commit'], ENT_QUOTES, 'UTF-8');
    $tags = htmlspecialchars($m['tags'], ENT_QUOTES, 'UTF-8');
    echo <<<HTML
    <div class="panel git-meta" id="git-meta">
      <strong>Git review</strong> · branch <code>{$branch}</code> · tree <code>{$dirty}</code><br>
      <strong>Version</strong> <code>{$version}</code><br>
      <strong>Latest</strong> <code>{$commit}</code><br>
      <strong>Tags</strong> <code>{$tags}</code>
    </div>
HTML;
}

function hub_render_foot(): void
{
    echo "</div>\n</body>\n</html>\n";
}

function hub_wrap_open(): void
{
    echo '<div class="wrap">';
}