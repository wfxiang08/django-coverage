# -*- encoding: utf-8 -*-
"""
Copyright 2009 55 Minutes (http://www.55minutes.com)

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import os, time
from django_coverage.utils.module_tools.data_storage import Authors

try:
    from urllib import pathname2url as p2url
except ImportError:
    from urllib.request import pathname2url as p2url

from django_coverage.utils.coverage_report.data_storage import ModuleVars
from django_coverage.utils.coverage_report.html_module_detail import html_module_detail
from django_coverage.utils.coverage_report.html_module_errors import html_module_errors
from django_coverage.utils.coverage_report.html_module_excludes import html_module_excludes
from django_coverage.utils.coverage_report.templates import default_module_index as module_index
from django_coverage import settings

def html_report(outdir, modules, excludes=None, errors=None):
    """
    Creates an ``index.html`` in the specified ``outdir``. Also attempts to create
    a ``modules`` subdirectory to create module detail html pages, which are named
    `module.__name__` + '.html'.

    It uses `templates.default_module_index` to create the index page. The template
    contains the following sections which need to be rendered and assembled into
    `index.html`.

    TOP: Contains the HTML declaration and head information, as well as the
         inline stylesheet. It doesn't require any variables.

    CONTENT_HEADER: The header portion of the body. Requires the following variable:
                    * ``%(test_timestamp)s``

    CONTENT_BODY: A table of contents to the different module detail pages, with some
                  basic stats. Requires the following variables:
                  * ``%(module_stats)s`` This is the actual content of the table and is
                    generated by looping through the modules we want to report on and
                    concatenanting together rendered ``MODULE_STAT`` template (see below).
                  * ``%(total_lines)d``
                  * ``%(total_executed)d``
                  * ``%(total_excluded)d``
                  * ``%(overall_covered)0.1f``

    EXCEPTIONS_LINK: Link to the excludes and errors index page which shows
                     packages and modules which were not part of the coverage
                     analysis. Requires the following variable:
                     * ``%(exceptions_link)s`` Link to the index page.
                     * ``%(exceptions_desc)s`` Describe the exception.

    ERRORS_LINK: Link to the errors index page which shows packages and modules which
                 had problems being imported. Requires the following variable:
                 * ``%(errors_link)s`` Link to the index page.

    BOTTOM: Just a closing ``</body></html>``

    MODULE_STAT: Used to assemble the content of ``%(module_stats)s`` for ``CONTENT_BODY``.
                 Requires the following variables:
                 * ``%(severity)s`` (normal, warning, critical) used as CSS class identifier
                   to style the coverage percentage.
                 * ``%(module_link)s``
                 * ``%(module_name)s``
                 * ``%(total_count)d``
                 * ``%(executed_count)d``
                 * ``%(excluded_count)d``
                 * ``%(percent_covered)0.1f``
    """
    test_timestamp = time.strftime('%a %Y-%m-%d %H:%M %Z')
    m_subdirname = 'modules'
    m_dir = os.path.join(outdir, m_subdirname)
    if not os.path.exists(m_dir):
        os.makedirs(m_dir)

    total_lines = 0
    total_executed = 0
    total_excluded = 0
    total_stmts = 0
    module_stats = list()

    m_names = list(modules.keys())
    m_names.sort()
    for n in m_names:
        m_vars = ModuleVars(n, modules[n])
        if not m_vars.total_count:
            excludes.append(m_vars.module_name)
            del modules[n]
            continue

        # 每个独立的moudle都会有自己的html报表
        m_vars.module_link = p2url(os.path.join(m_subdirname, m_vars.module_name + '.html'))
        module_stats.append(module_index.MODULE_STAT % m_vars.__dict__)
        total_lines += m_vars.total_count
        total_executed += m_vars.executed_count
        total_excluded += m_vars.excluded_count
        total_stmts += len(m_vars.stmts)
    module_stats = os.linesep.join(module_stats)
    if total_stmts:
        overall_covered = float(total_executed)/total_stmts*100
    else:
        overall_covered = 0.0

    # 单独处理每一个Modules
    m_names = list(modules.keys())
    m_names.sort()
    i = 0
    for i, n in enumerate(m_names):
        #
        # 链接关系:
        # index.html <---> module.html
        #
        m_vars = ModuleVars(n)
        nav = dict(up_link=p2url(os.path.join('..', 'index.html')), up_label='index')

        # module之间的前后关系
        if i > 0:
            m = ModuleVars(m_names[i-1])
            nav['prev_link'] = os.path.basename(m.module_link)
            nav['prev_label'] = m.module_name
        if i+1 < len(modules):
            m = ModuleVars(m_names[i+1])
            nav['next_link'] = os.path.basename(m.module_link)
            nav['next_label'] = m.module_name

        html_module_detail(os.path.join(m_dir, m_vars.module_name + '.html'), n, nav)

    # 以用户为中心输出统计结果:

    output_authors_html(outdir, test_timestamp, total_lines, total_executed, total_excluded, total_stmts, overall_covered)

    #
    # 统计结果的首页
    #
    fo = open(os.path.join(outdir, 'index.html'), 'w+')
    fo.write(module_index.TOP)
    # test_timestamp 当前的时间戳
    fo.write(module_index.CONTENT_HEADER % vars())
    fo.write(module_index.CONTENT_BODY % vars())

    if excludes:
        _file = 'excludes.html'
        exceptions_link = _file
        exception_desc = "Excluded packages and modules"
        fo.write(module_index.EXCEPTIONS_LINK % vars())
        html_module_excludes(os.path.join(outdir, _file), excludes)
    if errors:
        _file = 'errors.html'
        exceptions_link = _file
        exception_desc = "Error packages and modules"
        fo.write(module_index.EXCEPTIONS_LINK % vars())
        html_module_errors(os.path.join(outdir, _file), errors)
    fo.write(module_index.BOTTOM)
    fo.close()

    if settings.COVERAGE_BADGE_TYPE:
        badge = open(os.path.join(
            os.path.dirname(__file__),
            'badges',
            settings.COVERAGE_BADGE_TYPE,
            '%s.png' % int(overall_covered)
        ), 'rb').read()
        open(os.path.join(outdir, 'coverage_status.png'), 'wb').write(badge)

def output_authors_html(outdir, test_timestamp, total_lines, total_executed, total_excluded, total_stmts, overall_covered):


    m_subdirname = "author"
    m_dir = os.path.join(outdir, m_subdirname)
    if not os.path.exists(m_dir):
        os.makedirs(m_dir)

    authors_sig = Authors()
    author_2_modules = authors_sig.author_2_modules
    authors = author_2_modules.keys()
    authors.sort()

    module_stats = []
    for author in authors:
        module_link = p2url(os.path.join(m_subdirname, author + '.html'))
        module_name = author
        # executed, missed, excluded, total, "100%"
        executed_count, missed, excluded_count, total_count, percent_covered = authors_sig.get_author_summary(author)
        severity = 'normal'
        if percent_covered < 75: severity = 'warning'
        if percent_covered < 50: severity = 'critical'

        module_stats.append(module_index.MODULE_STAT % vars())

        output_author_html(outdir, authors_sig.author_2_modules[author], author)


    module_stats = os.linesep.join(module_stats)


    fo = open(os.path.join(outdir, 'auth_index.html'), 'w+')
    fo.write(module_index.TOP)
    # test_timestamp 当前的时间戳
    # fo.write(module_index.CONTENT_HEADER % vars())
    fo.write(module_index.CONTENT_BODY % vars())

    fo.write(module_index.BOTTOM)
    fo.close()

def output_author_html(outdir, modules, author):

    m_subdirname = "author"
    m_dir = os.path.join(outdir, m_subdirname)
    if not os.path.exists(m_dir):
        os.makedirs(m_dir)

    # authors_sig = Authors()
    # author_2_modules = authors_sig.author_2_modules
    # authors = author_2_modules.keys()
    # authors.sort()

    module_names = modules.keys()
    module_names.sort()

    module_stats = []
    for module_name in module_names:

        author_module = modules[module_name]
        module_link = author_module.module_link

        executed_count = author_module.executed
        missed = author_module.missed
        excluded = author_module.excluded
        percent_covered = executed_count / max((executed_count + missed), 1.0) * 100

        severity = 'normal'
        if percent_covered < 75: severity = 'warning'
        if percent_covered < 50: severity = 'critical'

        module_stats.append(module_index.MODULE_STAT % vars())


    module_stats = os.linesep.join(module_stats)


    fo = open(os.path.join(outdir, 'author', author + '.html'), 'w+')
    fo.write(module_index.TOP)
    # test_timestamp 当前的时间戳
    # fo.write(module_index.CONTENT_HEADER % vars())

    executed_count, missed, excluded_count, total_count, percent_covered = Authors().get_author_summary(author)
    severity = 'normal'
    if percent_covered < 75: severity = 'warning'
    if percent_covered < 50: severity = 'critical'
    fo.write(module_index.CONTENT_BODY % vars())

    fo.write(module_index.BOTTOM)
    fo.close()

