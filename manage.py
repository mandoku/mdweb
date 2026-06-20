#!/usr/bin/env python
import os
import click

COV = None
if os.environ.get('FLASK_COVERAGE'):
    import coverage
    COV = coverage.coverage(branch=True, include='app/*')
    COV.start()

if os.path.exists('.env'):
    print('Importing environment from .env...')
    for line in open('.env'):
        var = line.strip().split('=')
        if len(var) == 2:
            os.environ[var[0]] = var[1]

from app import create_app, db
from flask_migrate import Migrate, upgrade

app = create_app(os.getenv('FLASK_CONFIG') or 'default')
migrate = Migrate(app, db)


@app.shell_context_processor
def make_shell_context():
    return dict(app=app, db=db)


@app.cli.command("test")
@click.option('--coverage/--no-coverage', default=False)
def test(coverage):
    """Run the unit tests."""
    if coverage and not os.environ.get('FLASK_COVERAGE'):
        import sys
        os.environ['FLASK_COVERAGE'] = '1'
        os.execvp(sys.executable, [sys.executable] + sys.argv)
    import unittest
    tests = unittest.TestLoader().discover('tests')
    unittest.TextTestRunner(verbosity=2).run(tests)
    if COV:
        COV.stop()
        COV.save()
        print('Coverage Summary:')
        COV.report()
        basedir = os.path.abspath(os.path.dirname(__file__))
        covdir = os.path.join(basedir, 'tmp/coverage')
        COV.html_report(directory=covdir)
        print('HTML version: file://%s/index.html' % covdir)
        COV.erase()


@app.cli.command("profile")
@click.option('--length', default=25)
@click.option('--profile-dir', default=None)
def profile(length, profile_dir):
    """Start the application under the code profiler."""
    from werkzeug.middleware.profiler import ProfilerMiddleware
    app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[length],
                                      profile_dir=profile_dir)
    app.run()


@app.cli.command("deploy")
def deploy():
    """Run deployment tasks."""
    upgrade()


@app.cli.group()
def index():
    """Search-index commands."""
    pass


@index.command("build-text")
@click.argument('txtids', nargs=-1)
@click.option('--rebuild/--incremental', default=False,
              help="Remove and rewrite each per-text .krpx from scratch.")
@click.option('--quiet', is_flag=True, default=False,
              help="Suppress per-text progress output.")
def index_build_text(txtids, rebuild, quiet):
    """Build per-text .krpx files under KRPX_DIR.

    With no TXTIDS given, every text discovered under TXTDIR is built.
    """
    from app.indexer import build_text_index, build_all_text_indexes
    txtdir = app.config['TXTDIR']
    krpx_dir = app.config['KRPX_DIR']

    if txtids:
        total = 0
        for txtid in txtids:
            n = build_text_index(txtdir, krpx_dir, txtid, rebuild=rebuild)
            total += n
            if not quiet:
                click.echo(f"{txtid}  ({n} rows)")
        click.echo(f"Wrote {total} rows across {len(txtids)} .krpx file(s)")
        return

    def report(i, n_texts, txtid, total):
        if i == 1 or i == n_texts or i % 50 == 0:
            click.echo(f"[{i}/{n_texts}] {txtid}  ({total} rows)")

    n = build_all_text_indexes(txtdir, krpx_dir, rebuild=rebuild,
                               progress=None if quiet else report)
    click.echo(f"Wrote {n} rows into {krpx_dir}")


@index.command("merge")
@click.option('--rebuild/--incremental', default=False,
              help="Drop and rebuild the corpus FTS table from scratch.")
@click.option('--quiet', is_flag=True, default=False,
              help="Suppress per-file progress output.")
def index_merge(rebuild, quiet):
    """Merge all per-text .krpx files into the corpus kanripo.krpx."""
    from app.indexer import merge_indexes
    krpx_dir = app.config['KRPX_DIR']
    db_path = app.config['INDEX_DB_PATH']

    def report(i, n_files, path, total):
        if i == 1 or i == n_files or i % 50 == 0:
            click.echo(f"[{i}/{n_files}] {os.path.basename(path)}  ({total} rows)")

    n = merge_indexes(krpx_dir, db_path, rebuild=rebuild,
                      progress=None if quiet else report)
    click.echo(f"Merged {n} rows into {db_path}")


@index.command("build")
@click.option('--rebuild/--incremental', default=False,
              help="Drop and rebuild both per-text .krpx files and the corpus.")
@click.option('--quiet', is_flag=True, default=False,
              help="Suppress progress output.")
@click.pass_context
def index_build(ctx, rebuild, quiet):
    """Build every per-text .krpx and merge into the corpus (one-shot)."""
    ctx.invoke(index_build_text, txtids=(), rebuild=rebuild, quiet=quiet)
    ctx.invoke(index_merge, rebuild=rebuild, quiet=quiet)


@index.command("load-metadata")
def index_load_metadata():
    """Load catalog metadata and titles from MDBASE/system into SQLite."""
    from app.indexer import load_metadata
    db_path = app.config['INDEX_DB_PATH']
    mdbase = app.config['MDBASE']
    n = load_metadata(mdbase, db_path)
    click.echo(f"Loaded {n} metadata rows into {db_path}")


@index.command("build-taisho")
@click.option('--source', default=None,
              help="Path to mandoku-cbeta.el (defaults to TAISHO_SRC).")
def index_build_taisho(source):
    """Load the Taisho page→file index into SQLite."""
    from app.indexer import build_taisho_index
    src = source or app.config.get('TAISHO_SRC')
    if not src:
        raise click.UsageError(
            "No source provided; pass --source or set MDWEB_TAISHO_SRC."
        )
    db_path = app.config['INDEX_DB_PATH']
    n = build_taisho_index(src, db_path)
    click.echo(f"Loaded {n} taisho_pages rows into {db_path}")
