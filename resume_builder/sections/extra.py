"""
Extracurricular section — 100% static, never changes.
"""


def render() -> str:
    return r"""
    \section{Extracurricular Activities}

        \begin{onecolentry}
            \begin{highlightsforbulletentries}
                \item Won NYC Spark Hack (NVIDIA × Antler × Acer) and presented Person of Interest — a live VLM safety system on 900+ NYC traffic cameras — on NVIDIA AI LinkedIn Live
                \item Won 1st Place at NYC Hack \& Run 5K (May 2025) — built OpenMile, a real-time route analyzer scoring 953 NYC CCTV cameras via Llama 4 Scout and FastAPI, voice-coded mid-race
                \item Mentored 10+ participants at IC Hack IEEE India Council Hackathon 2023 in software development and teamwork
            \end{highlightsforbulletentries}
        \end{onecolentry}
"""
