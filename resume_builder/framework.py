"""
Static LaTeX preamble and document shell.
All formatting, packages, and custom environments live here.
Content sections are injected by the assembler.
"""

PREAMBLE = r"""\documentclass[10pt, letterpaper]{article}

% Packages:
\usepackage[
    ignoreheadfoot,
    top=0.5 cm,
    bottom=0.5 cm,
    left=0.5 cm,
    right=0.5 cm,
    footskip=1.0 cm,
]{geometry}
\usepackage{titlesec}
\usepackage{tabularx}
\usepackage{array}
\usepackage[dvipsnames]{xcolor}
\definecolor{primaryColor}{RGB}{0, 0, 0}
\usepackage{enumitem}
\usepackage{amsmath}

% XELATEX FONT SETUP
\usepackage{fontspec}
\setmainfont[
    Path=/Users/prath/Library/Fonts/,
    BoldFont=Carlito-Bold.ttf,
    ItalicFont=Carlito-Italic.ttf,
    BoldItalicFont=Carlito-BoldItalic.ttf
]{Carlito-Regular.ttf}

\usepackage[
    pdftitle={Pratham Saraf's CV},
    pdfauthor={Pratham Saraf},
    pdfcreator={LaTeX with RenderCV},
    colorlinks=true,
    urlcolor=primaryColor
]{hyperref}
\usepackage[pscoord]{eso-pic}
\usepackage{calc}
\usepackage{bookmark}
\usepackage{lastpage}
\usepackage{changepage}
\usepackage{paracol}
\usepackage{ifthen}
\usepackage{needspace}

% Settings:
\raggedright
\AtBeginEnvironment{adjustwidth}{\partopsep0pt}
\pagestyle{empty}
\setcounter{secnumdepth}{0}
\setlength{\parindent}{0pt}
\setlength{\topskip}{0pt}
\setlength{\columnsep}{0.15cm}
\pagenumbering{gobble}

\titleformat{\section}{\bfseries\large}{}{0pt}{}[\vspace{1pt}\titlerule]
\titlespacing{\section}{-1pt}{0.15 cm}{0.1 cm}

\renewcommand\labelitemi{$\vcenter{\hbox{\tiny$\bullet$}}$}
\newenvironment{highlights}{
    \begin{itemize}[
        topsep=0.05 cm,
        parsep=0.05 cm,
        partopsep=0pt,
        itemsep=0pt,
        leftmargin=0 cm + 10pt
    ]
}{\end{itemize}}

\newenvironment{highlightsforbulletentries}{
    \begin{itemize}[
        topsep=0.05 cm,
        parsep=0.05 cm,
        partopsep=0pt,
        itemsep=0pt,
        leftmargin=10pt
    ]
}{\end{itemize}}

\newenvironment{onecolentry}{
    \begin{adjustwidth}{0 cm + 0.00001 cm}{0 cm + 0.00001 cm}
}{\end{adjustwidth}}

\newenvironment{twocolentry}[2][]{
    \onecolentry
    \def\secondColumn{#2}
    \setcolumnwidth{\fill, 6.8 cm}
    \begin{paracol}{2}
}{
    \switchcolumn \raggedleft \secondColumn
    \end{paracol}
    \endonecolentry
}

\newenvironment{threecolentry}[3][]{
    \onecolentry
    \def\thirdColumn{#3}
    \setcolumnwidth{, \fill, 6.8 cm}
    \begin{paracol}{3}
    {\raggedright #2} \switchcolumn
}{
    \switchcolumn \raggedleft \thirdColumn
    \end{paracol}
    \endonecolentry
}

\newenvironment{header}{
    \setlength{\topsep}{0pt}\par\kern\topsep\centering\linespread{1.5}
}{\par\kern\topsep}

\let\hrefWithoutArrow\href
"""

DOCUMENT_OPEN = r"""
\begin{document}
    \newcommand{\AND}{\unskip
        \cleaders\copy\ANDbox\hskip\wd\ANDbox
        \ignorespaces
    }
    \newsavebox\ANDbox
    \sbox\ANDbox{$|$}
"""

DOCUMENT_CLOSE = r"""
\end{document}"""


COVER_PREAMBLE = r"""\documentclass[10pt, letterpaper]{article}

\usepackage[
    ignoreheadfoot,
    top=1.5 cm,
    bottom=1.5 cm,
    left=1.8cm,
    right=1.8 cm,
    footskip=1.0 cm,
]{geometry}
\usepackage{titlesec}
\usepackage[dvipsnames]{xcolor}
\definecolor{primaryColor}{RGB}{0, 0, 0}

\usepackage{fontspec}
\setmainfont{Times New Roman}

\usepackage[
    pdftitle={Pratham Saraf's Cover Letter},
    pdfauthor={Pratham Saraf},
    colorlinks=true,
    urlcolor=primaryColor
]{hyperref}

\pagestyle{empty}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0.8em}
"""
