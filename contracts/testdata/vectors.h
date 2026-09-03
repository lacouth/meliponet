// GERADO POR contracts/tools/gen_testdata.py -- NAO EDITE A MAO.
//
// Cada vetor traz as metricas ja como inteiros escalados (a representacao
// interna canonica do contrato) e o JSON exato que o codec deve produzir.
// Rode `python3 contracts/tools/gen_testdata.py` apos alterar o contrato.
#pragma once

#include "Scaling.h"
#include "TelemetryCodec.h"

namespace meliponet {
namespace testdata {

struct Vector {
  const char *name;
  Telemetry telemetry;
  const char *expected_json;
};

inline const Vector kVectors[] = {
    {
        "01_nominal",
        Telemetry{
            .node_id = "A4C1380F",
            .seq = 10432,
            .ts = "2027-03-14T12:05:00Z",
            .temp_in_c = 3012,
            .temp_out_c = 3480,
            .rh_in_pct = 6840,
            .rh_out_pct = 4120,
            .weight_kg = 12483,
            .vbat_v = 392,
            .rssi = -58,
            .present = Field::temp_in_c | Field::temp_out_c | Field::rh_in_pct | Field::rh_out_pct | Field::weight_kg | Field::vbat_v | Field::rssi,
        },
        "{\"schema\":\"meliponet.telemetry.v1\",\"node_id\":\"A4C1380F\",\"seq\":10432,\"ts\":\"2027-03-14T12:05:00Z\",\"temp_in_c\":30.12,\"temp_out_c\":34.80,\"rh_in_pct\":68.40,\"rh_out_pct\":41.20,\"weight_kg\":12.483,\"vbat_v\":3.92,\"rssi\":-58}",
    },
    {
        "02_arredondamento",
        Telemetry{
            .node_id = "A4C1380F",
            .seq = 10433,
            .ts = "2027-03-14T12:10:00Z",
            .temp_in_c = 3013,
            .temp_out_c = 0,
            .rh_in_pct = 10000,
            .rh_out_pct = 0,
            .weight_kg = 12500,
            .vbat_v = 400,
            .rssi = -58,
            .present = Field::temp_in_c | Field::temp_out_c | Field::rh_in_pct | Field::rh_out_pct | Field::weight_kg | Field::vbat_v | Field::rssi,
        },
        "{\"schema\":\"meliponet.telemetry.v1\",\"node_id\":\"A4C1380F\",\"seq\":10433,\"ts\":\"2027-03-14T12:10:00Z\",\"temp_in_c\":30.13,\"temp_out_c\":0.00,\"rh_in_pct\":100.00,\"rh_out_pct\":0.00,\"weight_kg\":12.500,\"vbat_v\":4.00,\"rssi\":-58}",
    },
    {
        "03_sht_externo_ausente",
        Telemetry{
            .node_id = "A4C1380F",
            .seq = 10434,
            .ts = "2027-03-14T12:15:00Z",
            .temp_in_c = 2987,
            .rh_in_pct = 7010,
            .weight_kg = 12481,
            .vbat_v = 391,
            .rssi = -61,
            .flags = Flag::sht_out_fault,
            .present = Field::temp_in_c | Field::rh_in_pct | Field::weight_kg | Field::vbat_v | Field::rssi,
        },
        "{\"schema\":\"meliponet.telemetry.v1\",\"node_id\":\"A4C1380F\",\"seq\":10434,\"ts\":\"2027-03-14T12:15:00Z\",\"temp_in_c\":29.87,\"rh_in_pct\":70.10,\"weight_kg\":12.481,\"vbat_v\":3.91,\"rssi\":-61,\"flags\":[\"sht_out_fault\"]}",
    },
    {
        "04_spool_relogio_bateria",
        Telemetry{
            .node_id = "7B21C904",
            .seq = 512,
            .ts = "2027-03-14T03:40:00Z",
            .temp_in_c = 2840,
            .temp_out_c = 2215,
            .rh_in_pct = 7400,
            .rh_out_pct = 8860,
            .weight_kg = 11902,
            .vbat_v = 341,
            .flags = Flag::spooled | Flag::low_batt | Flag::clock_unsynced,
            .present = Field::temp_in_c | Field::temp_out_c | Field::rh_in_pct | Field::rh_out_pct | Field::weight_kg | Field::vbat_v,
        },
        "{\"schema\":\"meliponet.telemetry.v1\",\"node_id\":\"7B21C904\",\"seq\":512,\"ts\":\"2027-03-14T03:40:00Z\",\"temp_in_c\":28.40,\"temp_out_c\":22.15,\"rh_in_pct\":74.00,\"rh_out_pct\":88.60,\"weight_kg\":11.902,\"vbat_v\":3.41,\"flags\":[\"low_batt\",\"clock_unsynced\",\"spooled\"]}",
    },
    {
        "05_somente_peso",
        Telemetry{
            .node_id = "7B21C904",
            .seq = 513,
            .ts = "2027-03-14T03:45:00Z",
            .weight_kg = 11900,
            .flags = Flag::sht_in_fault | Flag::sht_out_fault,
            .present = Field::weight_kg,
        },
        "{\"schema\":\"meliponet.telemetry.v1\",\"node_id\":\"7B21C904\",\"seq\":513,\"ts\":\"2027-03-14T03:45:00Z\",\"weight_kg\":11.900,\"flags\":[\"sht_in_fault\",\"sht_out_fault\"]}",
    },
    {
        "06_tara_negativa",
        Telemetry{
            .node_id = "7B21C904",
            .seq = 514,
            .ts = "2027-03-14T03:50:00Z",
            .temp_in_c = 2831,
            .weight_kg = -12,
            .vbat_v = 340,
            .flags = Flag::low_batt,
            .present = Field::temp_in_c | Field::weight_kg | Field::vbat_v,
        },
        "{\"schema\":\"meliponet.telemetry.v1\",\"node_id\":\"7B21C904\",\"seq\":514,\"ts\":\"2027-03-14T03:50:00Z\",\"temp_in_c\":28.31,\"weight_kg\":-0.012,\"vbat_v\":3.40,\"flags\":[\"low_batt\"]}",
    },
    {
        "07_no_completo_lora",
        Telemetry{
            .node_id = "C1090E22",
            .seq = 88291,
            .ts = "2027-06-02T15:00:00Z",
            .temp_in_c = 3144,
            .temp_out_c = 3890,
            .rh_in_pct = 6275,
            .rh_out_pct = 2830,
            .weight_kg = 18207,
            .vbat_v = 405,
            .rssi = -104,
            .snr = 75,
            .sound_rms = 18200,
            .sound_bands = {4120, 9805, 2333, 610},
            .gateway_id = "gw-jp-01",
            .present = Field::temp_in_c | Field::temp_out_c | Field::rh_in_pct | Field::rh_out_pct | Field::weight_kg | Field::vbat_v | Field::rssi | Field::snr | Field::sound_rms | Field::sound_bands | Field::gateway_id,
        },
        "{\"schema\":\"meliponet.telemetry.v1\",\"node_id\":\"C1090E22\",\"seq\":88291,\"ts\":\"2027-06-02T15:00:00Z\",\"temp_in_c\":31.44,\"temp_out_c\":38.90,\"rh_in_pct\":62.75,\"rh_out_pct\":28.30,\"weight_kg\":18.207,\"vbat_v\":4.05,\"rssi\":-104,\"snr\":7.5,\"sound_rms\":1820.0,\"sound_bands\":[412.0,980.5,233.3,61.0],\"gateway_id\":\"gw-jp-01\"}",
    },
};

inline constexpr size_t kVectorCount = sizeof(kVectors) / sizeof(kVectors[0]);

// Conversao leitura fisica -> inteiro escalado. O `expected` vem de
// canonical.quantize; o C++ precisa reproduzi-lo com meliponet::scale.
//
// As casas decimais vem de canonical.DECIMALS, a mesma tabela que o lado
// Python usa -- nao ha aqui uma segunda copia para sair de sincronia.
struct ScalingVector {
  double reading;
  int decimals;
  int32_t expected;
  const char *field;
};

inline const ScalingVector kScalingVectors[] = {
    {30.125, 2, 3013, "temp_in_c"},
    {8.615, 2, 862, "temp_in_c"},
    {-9.985, 2, -999, "temp_in_c"},
    {-0.004, 2, 0, "temp_in_c"},
    {30.12, 2, 3012, "temp_in_c"},
    {68.4, 2, 6840, "temp_in_c"},
    {-40.0, 2, -4000, "temp_in_c"},
    {85.0, 2, 8500, "temp_in_c"},
    {99.999, 2, 10000, "rh_in_pct"},
    {0.0, 2, 0, "rh_in_pct"},
    {33.335, 2, 3334, "rh_in_pct"},
    {12.5, 3, 12500, "weight_kg"},
    {12.483, 3, 12483, "weight_kg"},
    {-0.012, 3, -12, "weight_kg"},
    {0.0005, 3, 1, "weight_kg"},
    {49.9995, 3, 50000, "weight_kg"},
    {3.925, 2, 393, "vbat_v"},
    {4.0, 2, 400, "vbat_v"},
    {3.415, 2, 342, "vbat_v"},
};

inline constexpr size_t kScalingVectorCount =
    sizeof(kScalingVectors) / sizeof(kScalingVectors[0]);

}  // namespace testdata
}  // namespace meliponet
