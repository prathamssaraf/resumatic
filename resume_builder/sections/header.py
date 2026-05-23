"""
Header section — 100% static, pulled from graph.
"""
from graph import queries


def render() -> str:
    c = queries.get_candidate()
    return rf"""
    \begin{{header}}
        \fontsize{{20 pt}}{{20 pt}}\selectfont {c['name']}

        \vspace{{2 pt}}

        \normalsize
        \mbox{{{c['location']}}}%
        \kern 5.0 pt%
        \AND%
        \kern 5.0 pt%
        \mbox{{\hrefWithoutArrow{{mailto:{c['email']}}}{{{c['email']}}}}}%
        \kern 5.0 pt%
        \AND%
        \kern 5.0 pt%
        \mbox{{\hrefWithoutArrow{{tel:{c['phone'].replace(' ', '-')}}}{{{c['phone']}}}}}%
        \kern 5.0 pt%
        \AND%
        \kern 5.0 pt%
        \mbox{{\hrefWithoutArrow{{https://{c['github']}/}}{{{c['github']}}}}}%
        \kern 5.0 pt%
        \AND%
        \kern 5.0 pt%
        \mbox{{\hrefWithoutArrow{{https://linkedin.com/in/prathamssaraf}}{{linkedin.com/in/prathamssaraf}}}}%
    \end{{header}}

    \vspace{{5 pt - 0.3 cm}}
"""
