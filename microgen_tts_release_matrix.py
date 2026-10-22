"""Exhaustively verify autonomous and human-certified TTS release policy truth tables."""
from __future__ import annotations
import itertools,json
from microgen_tts_release_policy import decide_release,TECHNICAL_GATES,HUMAN_APPROVALS,AUTONOMOUS,HUMAN_CERTIFIED
class ReleaseMatrixFailure(AssertionError):pass
def verify_release_matrix()->dict:
    keys=TECHNICAL_GATES+HUMAN_APPROVALS
    checked=0;ready={"autonomous":0,"human-certified":0}
    for values in itertools.product((False,True),repeat=len(keys)):
        checks=dict(zip(keys,values))
        tech=all(checks[k] for k in TECHNICAL_GATES)
        manual=all(checks[k] for k in HUMAN_APPROVALS)
        for policy in (AUTONOMOUS,HUMAN_CERTIFIED):
            answer=decide_release(checks,policy)
            should_be_ready=tech and (manual if policy==HUMAN_CERTIFIED else True)
            assertions=(
                answer["automated_technical_qa_passed"]==tech,
                answer["human_qa_certified"]==manual,
                answer["ready_for_separate_promotion"]==should_be_ready,
                not answer["publication_performed"],
                answer["manual_approval_is_gate"]==(policy==HUMAN_CERTIFIED),
                answer["no_claim_of_human_review"]== (not manual),
            )
            if not all(assertions):
                raise ReleaseMatrixFailure("QA truth table drift for "+policy+" "+repr(checks))
            checked+=1;ready[policy]+=should_be_ready
    return {"schema_version":1,"technical_gates":len(TECHNICAL_GATES),
        "optional_human_checks":len(HUMAN_APPROVALS),
        "truth_table_scenarios":checked,
        "ready_scenarios_by_policy":ready,
        "policy_contract_consistent":True,
        "phonetic_correctness_proven":False,
        "publication_performed":False}
if __name__=="__main__":print(json.dumps(verify_release_matrix(),indent=2))
