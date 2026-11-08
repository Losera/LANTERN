# Alpha setup and operational constraints

Source: [Alpha reference, snapshot and attribution](research.md#source-manifest).
Imported November 7, 2026. This is an operational reference, not permission to
run its examples. No SSH, allocation, inference, serving, or Pi request was run
for this bootstrap.

## Evidence before readiness

| Boundary | Current basis | What would establish the next step |
| --- | --- | --- |
| SSH/MFA | User-reported access | Authorized session and dated observation, without secrets |
| Allocation | Observed November 7, 2026 UTC: [job 175560](../evidence/alpha/job-175560/README.md), H100 MIG 1g.10gb on alphagpu01 | Retained own-job receipt and MIG identity; parent memory is not allocated slice memory |
| GPU inference | Observed November 8, 2026 UTC: [tensor job 175757](../evidence/alpha/job-175757/README.md), [model job 175794](../evidence/alpha/job-175794/README.md), one BF16 Qwen3 response | Preserve the model-default sampling discrepancy; corrected greedy/full-budget diagnostic pending |
| Task competence | Not tested; waiting for agreed cases and issue 25's rules | Ten valid fixed-choice decisions from a fixed ten-attempt schedule; retain every failure |
| Throughput | Not tested | Timed bounded batch, attempts, token limits, errors, memory |
| Serving/network route | Not tested; optional | Site approval, node-local test, then approved client route |
| Pi subject integration | Not tested; optional | Completion, streaming, then benign tool test with actual access checked |

An installed CLI or working login does not establish GPU readiness. A completion
does not establish tool competence. A successful syntax check establishes neither.

## Allocation planning constraint

The source note cites the event-specific [Alpha allocation guide](https://empireai.freshdesk.com/support/solutions/articles/157000377792-binghamton-hackathon),
sections "What you're getting," "The three flags every job needs," and "Limits."
The planning session could not retrieve that page; confirm current rules with
organizers before allocating.

**Confirmed November 8, 2026:** the article was retrieved read-only and every
value in the snapshot table below matched, so no documented value has drifted.
The article records "Modified on Fri, 6 Nov at 4:54 PM" and an event window of
Friday, November 6 to Sunday, November 09. This reading came through a
summarizing fetch rather than a retained verbatim capture, so it is weaker
evidence than a hash-verified file; retain a verbatim capture before an
allocation decision cites it.

| Documented snapshot rule | Value |
| --- | --- |
| GPU slice | 10 GB MIG; request `--gres=gpu:1g.10gb:1` |
| Partition/reservation | `-p alpha --reservation=binghamton_hackathon` |
| Per-slice host resources | One CPU and at most 32 GB system RAM |
| Per-person running allocation | At most two slices across jobs |
| Wall time | Explicit limit, at most six hours |
| Pending plus running jobs | At most 50 |

Weights, activations, KV cache, and runtime overhead must fit the slice. Host RAM
is not extra VRAM; two slices do not provide one pooled 20 GB GPU. A parent H100
listing does not grant its full memory. No full-H100, Beta, installed framework,
cached model, exclusive host, or tracing privileges are established.

## Human-operated setup sequence

Read the [live hacker guide](https://docs.google.com/document/d/1A_yN6PBLpxP6pi_jx6evy6E3juQ5Wx8r_EVnKHujdqU/edit?tab=t.0)
and confirm the supported environment and model cache with organizers. Do not
invent module names or install a serving stack from a suggestion in these notes.

Only after authorization, replace `YOUR_USERNAME`; transfer the actual reviewed
experiment from the laptop. No `experiment.py` exists in this bootstrap:

```bash
ssh YOUR_USERNAME@alpha1.empireai.edu
# Run transfer from the laptop, not inside the remote shell:
scp experiment.py YOUR_USERNAME@alpha1.empireai.edu:~/
```

This proposed batch file checks identity only, not CUDA inference. Its ten-minute
budget is a proposal within the documented limit:

```bash
#!/bin/bash
#SBATCH -p alpha
#SBATCH --reservation=binghamton_hackathon
#SBATCH --gres=gpu:1g.10gb:1
#SBATCH -c 1
#SBATCH --mem=32G
#SBATCH -t 00:10:00
#SBATCH -J lantern-smoke
#SBATCH -o %x-%j.out
set -euo pipefail
nvidia-smi -L
```

Save a reviewed script as `alpha-smoke.sh` on Alpha before submission. The next
commands are human-operated examples, never an automatic helper action:

```bash
sbatch alpha-smoke.sh
squeue --me
```

If account selection fails, the snapshot recommends confirming `-A rpicourse`.
Cancel only your own job after checking its ID; no example cancellation is
provided to paste accidentally. GPU work belongs in an allocation, not on the
login host. Release an idle allocation rather than holding it for development.

## Inference and experiment gates

Confirm a site-supported GPU environment first. The research suggests
[Qwen2.5-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct)
as a candidate, not an approved or demonstrated model. Record revision, model
license, libraries, dtype, prompt/template, generation limits, and peak memory.
Do not install or download it merely because it appears here.

Establish one short GPU inference, then ten valid decisions, then timed batches.
Keep contexts and generations bounded. On OOM, inspect the measured allocation
and memory use before proposing a smaller model, context, or batch. Environment
and quantization changes require the appropriate review. Queue delay is not
inference latency. Latency/token counts do not measure energy or carbon savings.

Running an API-backed coding CLI on Alpha does not move provider inference to
Alpha. Copy back results and label actual execution provenance. If GPU access
fails, a permitted local/API or recorded fallback must be labeled accordingly;
it is not an Alpha run.

## Optional serving and Pi subject

Batch execution is the approved initial path. Only after a demonstrated need,
confirm serving/forwarding policy and test the node before an approved client
route. No tunnel or unauthenticated public endpoint is prescribed here.

The following is a complete JSON syntax example from the Pi 0.81.1 reference,
not a configuration installed by this project. Preserve existing providers if
later approved for manual integration. Port, model ID, auth, and limits are
illustrative; the URL requires an already approved working route:

```json
{
  "providers": {
    "alpha": {
      "baseUrl": "http://127.0.0.1:8080/v1",
      "api": "openai-completions",
      "apiKey": "$ALPHA_INFERENCE_API_KEY",
      "models": [{
        "id": "REPLACE_WITH_SERVED_MODEL_ID",
        "name": "Alpha experiment model",
        "contextWindow": 2048,
        "maxTokens": 512
      }]
    }
  }
}
```

`$ALPHA_INFERENCE_API_KEY` denotes an environment lookup in that Pi version;
without `$` it is a literal. Never commit a real key. The token limits do not
make weights fit VRAM. Check teammates' versions and the installed model docs.
After plain completion, separately test streaming and a harmless read-only tool
in a disposable shareable fixture. A tool allowlist is not an OS sandbox; inspect
extensions/settings and actual accessed files. Pi logs are trusted instrumentation,
not independent attestation. See [Pi model documentation](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/models.md).

## Source conflicts to resolve

The preserved PDF and live guide differ: the Saturday 11:59 pm project-form
deadline appears in the PDF but was absent from the retrieved live schedule.
The allocation article's "Sunday, November 09" header conflicts with the
November 7-8 event schedule. General and allocation-specific server descriptions
also differ. Confirm these rather than inferring a deadline extension or access.
Team eligibility, presentation duration, permitted advance preparation, and
pre-event Lean-artifact eligibility remain unresolved. Keep public source and
AI-use disclosure requirements visible. The [source manifest](research.md#source-manifest)
links the retained PDF without copying it into this repository.

**Status, November 8, 2026:** the allocation article was retrieved and states an
event window of Friday, November 6 to Sunday, November 09. That is wider than
the November 7-8 schedule recorded above rather than a contradictory date
header. The article contains no project-form deadline, so the PDF's Saturday
11:59 pm deadline remains uncorroborated. The live hacker guide returned only
the Google Docs application shell with no document text, so the schedule
difference, team eligibility, presentation duration, permitted advance
preparation, and pre-event Lean-artifact eligibility all remain unresolved.
