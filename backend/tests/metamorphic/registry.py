"""Registry of all Metamorphic Relations across SentinelCrypt subsystems."""
from __future__ import annotations

from typing import List

from backend.tests.metamorphic.canonicalization_relations import (
    MR_CAN_01_KeyShufflingInvariance,
    MR_CAN_02_WhitespaceNormalization,
    MR_CAN_03_TimezoneUTCNormalization,
    MR_CAN_04_NonFiniteFloatRejection,
)
from backend.tests.metamorphic.explanation_relations import (
    MR_EXP_01_NullFeatureZeroAttribution,
    MR_EXP_02_EfficiencyAxiomCompleteness,
    MR_EXP_03_LinearFeatureShiftAttribution,
    MR_EXP_04_StabilityNoiseMonotonicity,
    MR_EXP_05_ExplanationMetadataInvariance,
)
from backend.tests.metamorphic.framework import MetamorphicHarness, MetamorphicRelation
from backend.tests.metamorphic.hashing_relations import (
    MR_HASH_01_PreimageSensitivity,
    MR_HASH_02_ChainOperandNonCommutativity,
    MR_HASH_03_MerkleDomainSeparation,
    MR_HASH_04_MerkleOddLeafDuplication,
)
from backend.tests.metamorphic.prediction_relations import (
    MR_PRED_01_MetadataInvariance,
    MR_PRED_02_KeyOrderInvariance,
    MR_PRED_03_PositiveWeightFeatureMonotonicity,
    MR_PRED_04_BatchRowIsolation,
    MR_PRED_05_ConfidenceThresholdMonotonicity,
)
from backend.tests.metamorphic.preprocessing_relations import (
    MR_PRE_01_MetadataInvariance,
    MR_PRE_02_DictOrderInvariance,
    MR_PRE_03_UnseenCategoricalEquivalence,
    MR_PRE_04_BatchIsolationConsistency,
)
from backend.tests.metamorphic.verification_relations import (
    MR_VER_01_InductiveExtensionInvariance,
    MR_VER_02_SingleRecordTamperSensitivity,
    MR_VER_03_PrefixValidityUnderTruncation,
    MR_VER_04_NonGenesisSuffixRejection,
    MR_VER_05_NotaryPayloadDigestEntanglement,
)

ALL_RELATIONS: List[MetamorphicRelation] = [
    # Preprocessing (4)
    MR_PRE_01_MetadataInvariance(),
    MR_PRE_02_DictOrderInvariance(),
    MR_PRE_03_UnseenCategoricalEquivalence(),
    MR_PRE_04_BatchIsolationConsistency(),
    # Canonicalization (4)
    MR_CAN_01_KeyShufflingInvariance(),
    MR_CAN_02_WhitespaceNormalization(),
    MR_CAN_03_TimezoneUTCNormalization(),
    MR_CAN_04_NonFiniteFloatRejection(),
    # Cryptographic Hashing (4)
    MR_HASH_01_PreimageSensitivity(),
    MR_HASH_02_ChainOperandNonCommutativity(),
    MR_HASH_03_MerkleDomainSeparation(),
    MR_HASH_04_MerkleOddLeafDuplication(),
    # Evidence Verification (5)
    MR_VER_01_InductiveExtensionInvariance(),
    MR_VER_02_SingleRecordTamperSensitivity(),
    MR_VER_03_PrefixValidityUnderTruncation(),
    MR_VER_04_NonGenesisSuffixRejection(),
    MR_VER_05_NotaryPayloadDigestEntanglement(),
    # Prediction Behavior (5)
    MR_PRED_01_MetadataInvariance(),
    MR_PRED_02_KeyOrderInvariance(),
    MR_PRED_03_PositiveWeightFeatureMonotonicity(),
    MR_PRED_04_BatchRowIsolation(),
    MR_PRED_05_ConfidenceThresholdMonotonicity(),
    # Explanation Behavior (5)
    MR_EXP_01_NullFeatureZeroAttribution(),
    MR_EXP_02_EfficiencyAxiomCompleteness(),
    MR_EXP_03_LinearFeatureShiftAttribution(),
    MR_EXP_04_StabilityNoiseMonotonicity(),
    MR_EXP_05_ExplanationMetadataInvariance(),
]


def build_harness() -> MetamorphicHarness:
    """Build and populate a MetamorphicHarness with all registered relations."""
    harness = MetamorphicHarness()
    harness.register_many(ALL_RELATIONS)
    return harness
