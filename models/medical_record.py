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
    protesis: Optional[bool] = None # tinyint(1)
    caries: Optional[bool] = None
    encias_alteradas: Optional[bool] = None
    dentadura_parcial: Optional[bool] = None
    observations: Optional[str] = None

class MedicalRecordCardiovascularExam(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    freq_cardiaca: Optional[float] = None
    tension_arterial: Optional[float] = None
    ritmo_irregular: Optional[bool] = None
    ruidos_alterados: Optional[bool] = None
    extrasistoles: Optional[bool] = None
    soplos: Optional[bool] = None
    pulsos_perifericos_ausentes: Optional[bool] = None
    varices: Optional[bool] = None
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
    cicatrices_quirurgicas: Optional[bool] = None
    hemorroides: Optional[bool] = None
    dolores_abdominales: Optional[bool] = None
    hepatomegalia: Optional[bool] = None
    esplenomegalia: Optional[bool] = None
    adenopatias: Optional[bool] = None
    hernias: Optional[bool] = None
    observations: Optional[str] = None

class MedicalRecordEvaluationType(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    preocupational_exam: Optional[bool] = None
    graduation_exam: Optional[bool] = None
    post_enf_prolonged: Optional[bool] = None
    periodic_exams: Optional[bool] = None
    laboral_change_position: Optional[bool] = None
    sport_physical_aptitude: Optional[bool] = None
    other: Optional[str] = None

class MedicalRecordFamilyHistory(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    father_alive: Optional[bool] = None
    mother_alive: Optional[bool] = None
    brothers_alive: Optional[bool] = None
    sisters_alive: Optional[bool] = None
    husband_alive: Optional[bool] = None
    sons_alive: Optional[bool] = None
    mental_illnesses: Optional[bool] = None
    cardiovascular_illnesses: Optional[bool] = None
    kidney_problems: Optional[bool] = None
    digestive_problems: Optional[bool] = None
    asma: Optional[bool] = None
    tuberculosis: Optional[bool] = None
    diabetes: Optional[bool] = None
    reumatism: Optional[bool] = None
    cancer: Optional[bool] = None
    cancer_type: Optional[str] = None
    observations: Optional[str] = None

class MedicalRecordGenitourinarioExam(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    women_alteraciones_mamarias: Optional[bool] = None
    women_alteraciones_ginecologicas: Optional[bool] = None
    women_fum: Optional[bool] = None
    women_dolores_menstruales: Optional[bool] = None
    women_flujos_alterados: Optional[bool] = None
    women_anticonceptivos: Optional[bool] = None
    women_parto_normal: Optional[bool] = None
    women_abortos: Optional[bool] = None
    women_cesarea: Optional[bool] = None
    men_alteraciones_mamarias: Optional[bool] = None
    men_alteraciones_testiculares: Optional[bool] = None
    observations: Optional[str] = None

class MedicalRecordHabits(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    diet: Optional[bool] = None
    smoke: Optional[bool] = None
    smoke_quantity: Optional[int] = None
    alcoholic_drinks: Optional[bool] = None
    alcoholic_drinks_quantity: Optional[int] = None
    drugs: Optional[bool] = None
    drugs_type: Optional[str] = None
    sleep_alteration: Optional[bool] = None
    sleep_hours: Optional[int] = None
    daily_diet: Optional[bool] = None
    diet_type: Optional[str] = None
    physic_activity: Optional[bool] = None
    physic_activity_type: Optional[str] = None
    frequency: Optional[str] = None

class MedicalRecordHeadExam(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    alteration_movility: Optional[bool] = None
    latidos_carotideos_alterados: Optional[bool] = None
    tumoraciones_tiroideas: Optional[bool] = None
    adenopatias: Optional[bool] = None
    observations: Optional[str] = None

class MedicalRecordImmunizations(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    sars_cov_2: Optional[bool] = None
    sars_cov_2_dosis: Optional[int] = None
    fha: Optional[bool] = None
    triple_adultos_tetanos: Optional[bool] = None
    hepatitis_a: Optional[bool] = None
    hepatitis_b: Optional[bool] = None

class MedicalRecordLaboralContacts(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    dusty_environment: Optional[bool] = None
    dusty_environment_date: Optional[str] = None
    noisy_environment: Optional[bool] = None
    noisy_environment_date: Optional[str] = None
    animal_products: Optional[bool] = None
    animal_products_date: Optional[str] = None
    chemicals_products: Optional[bool] = None
    chemicals_products_date: Optional[str] = None
    ionizing_radiation: Optional[bool] = None
    ionizing_radiation_date: Optional[str] = None
    other_contamination: Optional[bool] = None
    other_contamination_date: Optional[str] = None

class MedicalRecordLaboralExam(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    physical: Optional[bool] = None
    chemical: Optional[bool] = None
    biological: Optional[bool] = None
    ergonomic: Optional[bool] = None
    others: Optional[bool] = None
    observations: Optional[str] = None

class MedicalRecordLaboralHistory(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    done_tasks: Optional[str] = None

class MedicalRecordNeuroClinicalExam(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    desorientado: Optional[bool] = None
    motilidad_alterada: Optional[bool] = None
    sensibilidad_alterada: Optional[bool] = None
    reflejos_alterados: Optional[bool] = None
    apraxia: Optional[bool] = None
    ataxia: Optional[bool] = None
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
    eyes_alterations: Optional[bool] = None
    discromatopsia: Optional[bool] = None
    observations: Optional[str] = None

class MedicalRecordOrlExam(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    faringe_pathology: Optional[bool] = None
    amigdalas_pathology: Optional[bool] = None
    voice_alterations: Optional[bool] = None
    rinitis: Optional[bool] = None
    audition_disorders: Optional[bool] = None
    adenopatias: Optional[bool] = None
    observations: Optional[str] = None

class MedicalRecordOsteoarticularExam(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    column_movilidad_alterada: Optional[bool] = None
    column_puntos_dolorosos: Optional[bool] = None
    column_escoliosis: Optional[bool] = None
    column_cifosis: Optional[bool] = None
    column_lordosis: Optional[bool] = None
    dolor_articular: Optional[bool] = None
    limitacion_movimientos: Optional[bool] = None
    tono_trofismo: Optional[bool] = None
    amputaciones: Optional[bool] = None
    movilidad_hombro_alterado: Optional[bool] = None
    movilidad_codo_alterado: Optional[bool] = None
    movilidad_muñeca_alterado: Optional[bool] = None
    movilidad_mano_alterado: Optional[bool] = None
    movilidad_cadera_alterado: Optional[bool] = None
    movilidad_rodilla_alterado: Optional[bool] = None
    movilidad_pie_alterado: Optional[bool] = None
    observations: Optional[str] = None

class MedicalRecordPersonalHistory(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    internations: Optional[bool] = None
    internations_motive: Optional[str] = None
    covid: Optional[bool] = None
    fha: Optional[bool] = None
    dengue: Optional[bool] = None

class MedicalRecordPreviousProblems(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    head_pain: Optional[bool] = None
    seizures: Optional[bool] = None
    dizziness_or_fainting: Optional[bool] = None
    excesive_nervious: Optional[bool] = None
    memory_loss: Optional[bool] = None
    eyes_problems: Optional[bool] = None
    ear_problems: Optional[bool] = None
    mouth_problems: Optional[bool] = None
    skin_diseases: Optional[bool] = None
    allergies: Optional[bool] = None
    sinusitis: Optional[bool] = None
    asma: Optional[bool] = None
    long_cough: Optional[bool] = None
    tuberculosis: Optional[bool] = None
    chest_pain: Optional[bool] = None
    insufficient_air: Optional[bool] = None
    palpitations: Optional[bool] = None
    high_or_low_pressure: Optional[bool] = None
    digestive_problems: Optional[bool] = None
    others: Optional[str] = None
    hepatitis: Optional[bool] = None
    hernias: Optional[bool] = None
    hemorroides: Optional[bool] = None
    difficulty_pee: Optional[bool] = None
    amputations: Optional[bool] = None
    bone_breaks: Optional[bool] = None
    neck_pain: Optional[bool] = None
    back_or_waist_pain: Optional[bool] = None
    shoulders_elbows_wrists_pain: Optional[bool] = None
    hips_knees_ankles_pain: Optional[bool] = None
    plane_feet: Optional[bool] = None
    varices: Optional[bool] = None
    diabetes: Optional[bool] = None
    fiebre_reumatica: Optional[bool] = None
    chagas: Optional[bool] = None
    sexual_transmition_diseases: Optional[bool] = None
    cancer: Optional[bool] = None
    medication_actually: Optional[bool] = None
    medication_type: Optional[str] = None

class MedicalRecordPsychiatricClinicalExam(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    alteraciones_conducta: Optional[bool] = None
    nerviosismo_excesivo: Optional[bool] = None
    depresion_psicomotriz: Optional[bool] = None
    timidez_excesiva: Optional[bool] = None
    observations: Optional[str] = None

class MedicalRecordRecomendations(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    apto: Optional[bool] = None
    apto_preexistencia_no_condiciona: Optional[bool] = None
    apto_preexistencia_condiciona: Optional[bool] = None
    no_apto_definitivo: Optional[bool] = None
    no_apto_temporal: Optional[bool] = None
    duracion: Optional[str] = None
    observations: Optional[str] = None

class MedicalRecordRespiratorioExam(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    freq_respiratoria: Optional[float] = None
    deformaciones_toracicas: Optional[bool] = None
    rales: Optional[bool] = None
    roncus: Optional[bool] = None
    murmullo_vesicular: Optional[bool] = None
    adenopatias: Optional[bool] = None
    proceso_agudo: Optional[bool] = None
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
    skin_alteration: Optional[bool] = None
    piercing: Optional[bool] = None
    tattoo: Optional[bool] = None
    cicatrices: Optional[bool] = None
    observations: Optional[str] = None

class MedicalRecordStudies(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    rx_torax_frente: Optional[bool] = None
    rx_columna_lumbo_sacra_frente: Optional[bool] = None
    rx_columna_cervical_frente: Optional[bool] = None
    electro: Optional[bool] = None
    audiometria: Optional[bool] = None
    psicotecnico: Optional[bool] = None
    espirometria: Optional[bool] = None
    ergometria: Optional[bool] = None
    evaluation_oftalmologica: Optional[bool] = None
    psicometria: Optional[bool] = None
    electroencefalograma: Optional[bool] = None
    laboratorio: Optional[bool] = None
    drogas_abuso: Optional[bool] = None
    test_cereal: Optional[bool] = None
    observations: Optional[str] = None

class MedicalRecordSurgerys(BaseModel):
    id: Optional[str] = None
    medical_record_id: Optional[str] = None
    apendice: Optional[bool] = None
    apendice_date: Optional[str] = None
    amigdala: Optional[bool] = None
    amigdala_date: Optional[str] = None
    hernia: Optional[bool] = None
    hernia_date: Optional[str] = None
    varices: Optional[bool] = None
    varices_date: Optional[str] = None
    vesicula: Optional[bool] = None
    vesicula_date: Optional[str] = None
    columna: Optional[bool] = None
    columna_date: Optional[str] = None
    testiculos: Optional[bool] = None
    testiculos_date: Optional[str] = None
    others: Optional[bool] = None
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
