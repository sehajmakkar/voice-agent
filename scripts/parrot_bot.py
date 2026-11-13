"""Parrot bot (plan 0.6): talk in the browser, hear yourself played back when you stop.

    uv run python scripts/parrot_bot.py
    then open http://localhost:7860 and press Connect (use headphones)

Pipeline (frames flow top to bottom; see L-009):

    transport.input()     browser mic → InputAudioRawFrame every 20 ms
    FrameLogger("in")     shows what arrives
    VADProcessor          Silero VAD → VADUserStarted/StoppedSpeakingFrame
    Parrot                buffers your speech, replays it as OutputAudioRawFrame
    FrameLogger("out")    shows what's about to be played
    transport.output()    → browser speaker
"""

from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.audio.vad_processor import VADProcessor
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.transports.base_transport import TransportParams
from pipecat.workers.runner import WorkerRunner

from swar.pipeline.frame_logger import FrameLogger
from swar.pipeline.parrot import Parrot

RATE = 16_000
# Silero's default stop_secs is 0.2 s, which cuts Hinglish speakers off mid-thought
# ("matlab... woh..."). 0.6 s is gentler; this trade-off is the subject of Phase 8.
STOP_SECS = 0.6


async def bot(runner_args: RunnerArguments) -> None:
    transport = await create_transport(
        runner_args,
        {"webrtc": lambda: TransportParams(audio_in_enabled=True, audio_out_enabled=True)},
    )
    vad = VADProcessor(vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=STOP_SECS)))
    pipeline = Pipeline(
        [
            transport.input(),
            FrameLogger("in"),
            vad,
            Parrot(),
            FrameLogger("out"),
            transport.output(),
        ]
    )
    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(audio_in_sample_rate=RATE, audio_out_sample_rate=RATE),
    )
    runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client) -> None:
        logger.info("Browser connected: say something, then pause")

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client) -> None:
        logger.info("Browser disconnected")
        await runner.cancel()

    await runner.add_workers(worker)
    await runner.run()


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
