from pydantic import BaseModel, Field, model_validator
from typing import Optional, List, Any
import json
from datetime import datetime

# -------------------------------------------------------------------
# Tablas individuales
# -------------------------------------------------------------------

class MedicalRecordBucodentalExam(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    protesis: Optional[int] = None # tinyint(1)
    caries: Optional[int] = None
    encias_alteradas: Optional[int] = None
    dentadura_parcial: Optional[int] = None
    observations: Optional[str] = None

class MedicalRecordCardiovascularExam(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    freq_cardiaca: Optional[float] = None
    tension_arterial: Optional[float] = None
    ritmo_irregular: Optional[int] = None
    ruidos_alterados: Optional[int] = None
    extrasistoles: Optional[int] = None
    soplos: Optional[int] = None
    pulsos_perifericos_ausentes: Optional[int] = None
    varices: Optional[int] = None
    observations: Optional[str] = None

class MedicalRecordClinicalExam(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    talla: Optional[float] = None
    peso: Optional[float] = None
    saturacion: Optional[float] = None
    imc: Optional[float] = None
    ta_min: Optional[float] = None
    ta_max: Optional[float] = None

class MedicalRecordData(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    complete_name: Optional[str] = None
    dni: Optional[int] = None
    address: Optional[str] = None
    date_of_birthday: Optional[str] = None
    nacionality: Optional[str] = None
    email: Optional[str] = None
    civil_status: Optional[str] = None
    phone: Optional[int] = None
    sons: Optional[int] = None
    tasks: Optional[str] = None

class MedicalRecordDataImg(BaseModel):
    id: Optional[str] = None
    medical_record_data_id: Optional[str] = None
    url: Optional[str] = None

class MedicalRecordDerivations(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    derivations_lastname_especialists: Optional[str] = None

class MedicalRecordDigestiveExam(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    cicatrices_quirurgicas: Optional[int] = None
    hemorroides: Optional[int] = None
    dolores_abdominales: Optional[int] = None
    hepatomegalia: Optional[int] = None
    esplenomegalia: Optional[int] = None
    adenopatias: Optional[int] = None
    hernias: Optional[int] = None
    observations: Optional[str] = None

class MedicalRecordEvaluationType(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    preocupational_exam: Optional[int] = None
    graduation_exam: Optional[int] = None
    post_enf_prolonged: Optional[int] = None
    periodic_exams: Optional[int] = None
    laboral_change_position: Optional[int] = None
    sport_physical_aptitude: Optional[int] = None
    other: Optional[str] = None

class MedicalRecordFamilyHistory(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    father_alive: Optional[int] = None
    mother_alive: Optional[int] = None
    brothers_alive: Optional[int] = None
    sisters_alive: Optional[int] = None
    husband_alive: Optional[int] = None
    sons_alive: Optional[int] = None
    mental_illnesses: Optional[int] = None
    cardiovascular_illnesses: Optional[int] = None
    kidney_problems: Optional[int] = None
    digestive_problems: Optional[int] = None
    asma: Optional[int] = None
    tuberculosis: Optional[int] = None
    diabetes: Optional[int] = None
    reumatism: Optional[int] = None
    cancer: Optional[int] = None
    cancer_type: Optional[str] = None
    observations: Optional[str] = None

class MedicalRecordGenitourinarioExam(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    women_alteraciones_mamarias: Optional[int] = None
    women_alteraciones_ginecologicas: Optional[int] = None
    women_fum: Optional[int] = None
    women_dolores_menstruales: Optional[int] = None
    women_flujos_alterados: Optional[int] = None
    women_anticonceptivos: Optional[int] = None
    women_parto_normal: Optional[int] = None
    women_abortos: Optional[int] = None
    women_cesarea: Optional[int] = None
    men_alteraciones_mamarias: Optional[int] = None
    men_alteraciones_testiculares: Optional[int] = None
    observations: Optional[str] = None

class MedicalRecordHabits(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    diet: Optional[int] = None
    smoke: Optional[int] = None
    smoke_quantity: Optional[int] = None
    alcoholic_drinks: Optional[int] = None
    alcoholic_drinks_quantity: Optional[int] = None
    drugs: Optional[int] = None
    drugs_type: Optional[str] = None
    sleep_alteration: Optional[int] = None
    sleep_hours: Optional[int] = None
    daily_diet: Optional[int] = None
    diet_type: Optional[str] = None
    physic_activity: Optional[int] = None
    physic_activity_type: Optional[str] = None
    frequency: Optional[str] = None

class MedicalRecordHeadExam(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    alteration_movility: Optional[int] = None
    latidos_carotideos_alterados: Optional[int] = None
    tumoraciones_tiroideas: Optional[int] = None
    adenopatias: Optional[int] = None
    observations: Optional[str] = None

class MedicalRecordImmunizations(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    sars_cov_2: Optional[int] = None
    sars_cov_2_dosis: Optional[int] = None
    fha: Optional[int] = None
    triple_adultos_tetanos: Optional[int] = None
    hepatitis_a: Optional[int] = None
    hepatitis_b: Optional[int] = None

class MedicalRecordLaboralContacts(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    dusty_environment: Optional[int] = None
    dusty_environment_date: Optional[str] = None
    noisy_environment: Optional[int] = None
    noisy_environment_date: Optional[str] = None
    animal_products: Optional[int] = None
    animal_products_date: Optional[str] = None
    chemicals_products: Optional[int] = None
    chemicals_products_date: Optional[str] = None
    ionizing_radiation: Optional[int] = None
    ionizing_radiation_date: Optional[str] = None
    other_contamination: Optional[int] = None
    other_contamination_date: Optional[str] = None

class MedicalRecordLaboralExam(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    physical: Optional[int] = None
    chemical: Optional[int] = None
    biological: Optional[int] = None
    ergonomic: Optional[int] = None
    others: Optional[int] = None
    observations: Optional[str] = None

class MedicalRecordLaboralHistory(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    done_tasks: Optional[str] = None

class MedicalRecordNeuroClinicalExam(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    desorientado: Optional[int] = None
    motilidad_alterada: Optional[int] = None
    sensibilidad_alterada: Optional[int] = None
    reflejos_alterados: Optional[int] = None
    apraxia: Optional[int] = None
    ataxia: Optional[int] = None
    observations: Optional[str] = None

class MedicalRecordOftalmologicoExam(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    sc_od_nearby: Optional[float] = None
    sc_oi_nearby: Optional[float] = None
    cc_od_nearby: Optional[float] = None
    cc_oi_nearby: Optional[float] = None
    sc_od_distant: Optional[float] = None
    sc_oi_distant: Optional[float] = None
    cc_od_distant: Optional[float] = None
    cc_oi_distant: Optional[float] = None
    eyes_alterations: Optional[int] = None
    discromatopsia: Optional[int] = None
    observations: Optional[str] = None

class MedicalRecordOrlExam(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    faringe_pathology: Optional[int] = None
    amigdalas_pathology: Optional[int] = None
    voice_alterations: Optional[int] = None
    rinitis: Optional[int] = None
    audition_disorders: Optional[int] = None
    adenopatias: Optional[int] = None
    observations: Optional[str] = None

class MedicalRecordOsteoarticularExam(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    column_movilidad_alterada: Optional[int] = None
    column_puntos_dolorosos: Optional[int] = None
    column_escoliosis: Optional[int] = None
    column_cifosis: Optional[int] = None
    column_lordosis: Optional[int] = None
    dolor_articular: Optional[int] = None
    limitacion_movimientos: Optional[int] = None
    tono_trofismo: Optional[int] = None
    amputaciones: Optional[int] = None
    movilidad_hombro_alterado: Optional[int] = None
    movilidad_codo_alterado: Optional[int] = None
    movilidad_muñeca_alterado: Optional[int] = None
    movilidad_mano_alterado: Optional[int] = None
    movilidad_cadera_alterado: Optional[int] = None
    movilidad_rodilla_alterado: Optional[int] = None
    movilidad_pie_alterado: Optional[int] = None
    observations: Optional[str] = None

class MedicalRecordPersonalHistory(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    internations: Optional[int] = None
    internations_motive: Optional[str] = None
    covid: Optional[int] = None
    fha: Optional[int] = None
    dengue: Optional[int] = None

class MedicalRecordPreviousProblems(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    head_pain: Optional[int] = None
    seizures: Optional[int] = None
    dizziness_or_fainting: Optional[int] = None
    excesive_nervious: Optional[int] = None
    memory_loss: Optional[int] = None
    eyes_problems: Optional[int] = None
    ear_problems: Optional[int] = None
    mouth_problems: Optional[int] = None
    skin_diseases: Optional[int] = None
    allergies: Optional[int] = None
    sinusitis: Optional[int] = None
    asma: Optional[int] = None
    long_cough: Optional[int] = None
    tuberculosis: Optional[int] = None
    chest_pain: Optional[int] = None
    insufficient_air: Optional[int] = None
    palpitations: Optional[int] = None
    high_or_low_pressure: Optional[int] = None
    digestive_problems: Optional[int] = None
    others: Optional[str] = None
    hepatitis: Optional[int] = None
    hernias: Optional[int] = None
    hemorroides: Optional[int] = None
    difficulty_pee: Optional[int] = None
    amputations: Optional[int] = None
    bone_breaks: Optional[int] = None
    neck_pain: Optional[int] = None
    back_or_waist_pain: Optional[int] = None
    shoulders_elbows_wrists_pain: Optional[int] = None
    hips_knees_ankles_pain: Optional[int] = None
    plane_feet: Optional[int] = None
    varices: Optional[int] = None
    diabetes: Optional[int] = None
    fiebre_reumatica: Optional[int] = None
    chagas: Optional[int] = None
    sexual_transmition_diseases: Optional[int] = None
    cancer: Optional[int] = None
    medication_actually: Optional[int] = None
    medication_type: Optional[str] = None

class MedicalRecordPsychiatricClinicalExam(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    alteraciones_conducta: Optional[int] = None
    nerviosismo_excesivo: Optional[int] = None
    depresion_psicomotriz: Optional[int] = None
    timidez_excesiva: Optional[int] = None
    observations: Optional[str] = None

class MedicalRecordRecomendations(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    apto: Optional[int] = None
    apto_preexistencia_no_condiciona: Optional[int] = None
    apto_preexistencia_condiciona: Optional[int] = None
    no_apto_definitivo: Optional[int] = None
    no_apto_temporal: Optional[int] = None
    duracion: Optional[str] = None
    observations: Optional[str] = None

class MedicalRecordRespiratorioExam(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    freq_respiratoria: Optional[float] = None
    deformaciones_toracicas: Optional[int] = None
    rales: Optional[int] = None
    roncus: Optional[int] = None
    murmullo_vesicular: Optional[int] = None
    adenopatias: Optional[int] = None
    proceso_agudo: Optional[int] = None
    observations: Optional[str] = None

class MedicalRecordSignatures(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    url: Optional[str] = None
    professional_id: Optional[str] = None
    created_at: Optional[datetime] = None

class MedicalRecordSkinExam(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    skin_alteration: Optional[int] = None
    piercing: Optional[int] = None
    tattoo: Optional[int] = None
    cicatrices: Optional[int] = None
    observations: Optional[str] = None

class MedicalRecordStudies(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    rx_torax_frente: Optional[int] = None
    rx_columna_lumbo_sacra_frente: Optional[int] = None
    rx_columna_cervical_frente: Optional[int] = None
    electro: Optional[int] = None
    audiometria: Optional[int] = None
    psicotecnico: Optional[int] = None
    espirometria: Optional[int] = None
    ergometria: Optional[int] = None
    evaluation_oftalmologica: Optional[int] = None
    psicometria: Optional[int] = None
    electroencefalograma: Optional[int] = None
    laboratorio: Optional[int] = None
    drogas_abuso: Optional[int] = None
    test_cereal: Optional[int] = None
    observations: Optional[str] = None

class MedicalRecordSurgerys(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    apendice: Optional[int] = None
    apendice_date: Optional[str] = None
    amigdala: Optional[int] = None
    amigdala_date: Optional[str] = None
    hernia: Optional[int] = None
    hernia_date: Optional[str] = None
    varices: Optional[int] = None
    varices_date: Optional[str] = None
    vesicula: Optional[int] = None
    vesicula_date: Optional[str] = None
    columna: Optional[int] = None
    columna_date: Optional[str] = None
    testiculos: Optional[int] = None
    testiculos_date: Optional[str] = None
    others: Optional[int] = None
    others_date: Optional[str] = None

# -------------------------------------------------------------------
# Request / Response Unificados
# -------------------------------------------------------------------

class MedicalRecordFullRequest(BaseModel):
    # medical_record (parent) NO TIENE CAMPOS PROPIOS MÁS QUE IDs en el SQL
    
    medical_record_bucodental_exam: Optional[MedicalRecordBucodentalExam] = Field(None, description="**Medical Record Bucodental Exam**")
    medical_record_cardiovascular_exam: Optional[MedicalRecordCardiovascularExam] = Field(None, description="**Medical Record Cardiovascular Exam**")
    medical_record_clinical_exam: Optional[MedicalRecordClinicalExam] = Field(None, description="**Medical Record Clinical Exam**")
    medical_record_data: Optional[MedicalRecordData] = Field(None, description="**Medical Record Data**")
    medical_record_data_img: Optional[MedicalRecordDataImg] = Field(None, description="**Medical Record Data Img**")
    medical_record_derivations: Optional[MedicalRecordDerivations] = Field(None, description="**Medical Record Derivations**")
    medical_record_digestive_exam: Optional[MedicalRecordDigestiveExam] = Field(None, description="**Medical Record Digestive Exam**")
    medical_record_evaluation_type: Optional[MedicalRecordEvaluationType] = Field(None, description="**Medical Record Evaluation Type**")
    medical_record_family_history: Optional[MedicalRecordFamilyHistory] = Field(None, description="**Medical Record Family History**")
    medical_record_genitourinario_exam: Optional[MedicalRecordGenitourinarioExam] = Field(None, description="**Medical Record Genitourinario Exam**")
    medical_record_habits: Optional[MedicalRecordHabits] = Field(None, description="**Medical Record Habits**")
    medical_record_head_exam: Optional[MedicalRecordHeadExam] = Field(None, description="**Medical Record Head Exam**")
    medical_record_immunizations: Optional[MedicalRecordImmunizations] = Field(None, description="**Medical Record Immunizations**")
    medical_record_laboral_contacts: Optional[MedicalRecordLaboralContacts] = Field(None, description="**Medical Record Laboral Contacts**")
    medical_record_laboral_exam: Optional[MedicalRecordLaboralExam] = Field(None, description="**Medical Record Laboral Exam**")
    medical_record_laboral_history: Optional[MedicalRecordLaboralHistory] = Field(None, description="**Medical Record Laboral History**")
    medical_record_neuro_clinical_exam: Optional[MedicalRecordNeuroClinicalExam] = Field(None, description="**Medical Record Neuro Clinical Exam**")
    medical_record_oftalmologico_exam: Optional[MedicalRecordOftalmologicoExam] = Field(None, description="**Medical Record Oftalmologico Exam**")
    medical_record_orl_exam: Optional[MedicalRecordOrlExam] = Field(None, description="**Medical Record Orl Exam**")
    medical_record_osteoarticular_exam: Optional[MedicalRecordOsteoarticularExam] = Field(None, description="**Medical Record Osteoarticular Exam**")
    medical_record_personal_history: Optional[MedicalRecordPersonalHistory] = Field(None, description="**Medical Record Personal History**")
    medical_record_previous_problems: Optional[MedicalRecordPreviousProblems] = Field(None, description="**Medical Record Previous Problems**")
    medical_record_psychiatric_clinical_exam: Optional[MedicalRecordPsychiatricClinicalExam] = Field(None, description="**Medical Record Psychiatric Clinical Exam**")
    medical_record_recomendations: Optional[MedicalRecordRecomendations] = Field(None, description="**Medical Record Recomendations**")
    medical_record_respiratorio_exam: Optional[MedicalRecordRespiratorioExam] = Field(None, description="**Medical Record Respiratorio Exam**")
    # medical_record_signatures: Se maneja aparte con la imagen
    medical_record_skin_exam: Optional[MedicalRecordSkinExam] = Field(None, description="**Medical Record Skin Exam**")
    medical_record_studies: Optional[MedicalRecordStudies] = Field(None, description="**Medical Record Studies**")
    medical_record_surgerys: Optional[MedicalRecordSurgerys] = Field(None, description="**Medical Record Surgerys**")

    @model_validator(mode='before')
    @classmethod
    def validate_to_json(cls, value: Any) -> Any:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON string: {e}")
        return value


class MedicalRecordFullResponse(BaseModel):
    id: str
    patient_id: str
    
    medical_record_bucodental_exam: Optional[MedicalRecordBucodentalExam] = Field(None, description="**Medical Record Bucodental Exam**")
    medical_record_cardiovascular_exam: Optional[MedicalRecordCardiovascularExam] = Field(None, description="**Medical Record Cardiovascular Exam**")
    medical_record_clinical_exam: Optional[MedicalRecordClinicalExam] = Field(None, description="**Medical Record Clinical Exam**")
    medical_record_data: Optional[MedicalRecordData] = Field(None, description="**Medical Record Data**")
    medical_record_data_img: Optional[MedicalRecordDataImg] = Field(None, description="**Medical Record Data Img**")
    medical_record_derivations: Optional[MedicalRecordDerivations] = Field(None, description="**Medical Record Derivations**")
    medical_record_digestive_exam: Optional[MedicalRecordDigestiveExam] = Field(None, description="**Medical Record Digestive Exam**")
    medical_record_evaluation_type: Optional[MedicalRecordEvaluationType] = Field(None, description="**Medical Record Evaluation Type**")
    medical_record_family_history: Optional[MedicalRecordFamilyHistory] = Field(None, description="**Medical Record Family History**")
    medical_record_genitourinario_exam: Optional[MedicalRecordGenitourinarioExam] = Field(None, description="**Medical Record Genitourinario Exam**")
    medical_record_habits: Optional[MedicalRecordHabits] = Field(None, description="**Medical Record Habits**")
    medical_record_head_exam: Optional[MedicalRecordHeadExam] = Field(None, description="**Medical Record Head Exam**")
    medical_record_immunizations: Optional[MedicalRecordImmunizations] = Field(None, description="**Medical Record Immunizations**")
    medical_record_laboral_contacts: Optional[MedicalRecordLaboralContacts] = Field(None, description="**Medical Record Laboral Contacts**")
    medical_record_laboral_exam: Optional[MedicalRecordLaboralExam] = Field(None, description="**Medical Record Laboral Exam**")
    medical_record_laboral_history: Optional[MedicalRecordLaboralHistory] = Field(None, description="**Medical Record Laboral History**")
    medical_record_neuro_clinical_exam: Optional[MedicalRecordNeuroClinicalExam] = Field(None, description="**Medical Record Neuro Clinical Exam**")
    medical_record_oftalmologico_exam: Optional[MedicalRecordOftalmologicoExam] = Field(None, description="**Medical Record Oftalmologico Exam**")
    medical_record_orl_exam: Optional[MedicalRecordOrlExam] = Field(None, description="**Medical Record Orl Exam**")
    medical_record_osteoarticular_exam: Optional[MedicalRecordOsteoarticularExam] = Field(None, description="**Medical Record Osteoarticular Exam**")
    medical_record_personal_history: Optional[MedicalRecordPersonalHistory] = Field(None, description="**Medical Record Personal History**")
    medical_record_previous_problems: Optional[MedicalRecordPreviousProblems] = Field(None, description="**Medical Record Previous Problems**")
    medical_record_psychiatric_clinical_exam: Optional[MedicalRecordPsychiatricClinicalExam] = Field(None, description="**Medical Record Psychiatric Clinical Exam**")
    medical_record_recomendations: Optional[MedicalRecordRecomendations] = Field(None, description="**Medical Record Recomendations**")
    medical_record_respiratorio_exam: Optional[MedicalRecordRespiratorioExam] = Field(None, description="**Medical Record Respiratorio Exam**")
    medical_record_signatures: Optional[MedicalRecordSignatures] = Field(None, description="**Medical Record Signatures**")
    medical_record_skin_exam: Optional[MedicalRecordSkinExam] = Field(None, description="**Medical Record Skin Exam**")
    medical_record_studies: Optional[MedicalRecordStudies] = Field(None, description="**Medical Record Studies**")
    medical_record_surgerys: Optional[MedicalRecordSurgerys] = Field(None, description="**Medical Record Surgerys**")
