#include "shadowrun_dialogs.h"

#include "genesis_runtime.h"
#include "glue.h"

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#include <windows.h>
#endif

typedef struct {
    uint8_t id;
    uint32_t node;
    uint32_t actor;
    const char *name;
} ShadowrunDialogEntry;

static const ShadowrunDialogEntry shadowrun_dialog_catalog[] = {
    { 0x00u, 0x1113D2u, 0x122030u, "Hollywood Correctional Facility gate" },
    { 0x01u, 0x0F4B4Cu, 0x121E14u, "Tribal council building" },
    { 0x02u, 0x11B5D8u, 0x122024u, "Elven guard gate" },
    { 0x03u, 0x110AC2u, 0x122024u, "Package delivery" },
    { 0x04u, 0x110ABAu, 0x122024u, "Package pickup" },
    { 0x05u, 0x110A96u, 0x122024u, "Icarus Descending restaurant" },
    { 0x06u, 0x110AD2u, 0x121F34u, "Guard package delivery" },
    { 0x07u, 0x110ACAu, 0x121F34u, "Guard package pickup" },
    { 0x08u, 0x110ADAu, 0x121F34u, "Matchstick nightclub" },
    { 0x09u, 0x11139Au, 0x12209Cu, "Guard package inspection" },
    { 0x0Au, 0x111392u, 0x12209Cu, "Guard package handoff" },
    { 0x0Bu, 0x110CB2u, 0x12209Cu, "Mitsuhama office" },
    { 0x0Cu, 0x110B7Eu, 0x122090u, "Fuchi guard package delivery" },
    { 0x0Du, 0x110B76u, 0x122090u, "Fuchi guard package pickup" },
    { 0x0Eu, 0x110B86u, 0x122090u, "Fuchi Industrial Electronics" },
    { 0x0Fu, 0x110B6Eu, 0x1220B4u, "Bartender package delivery" },
    { 0x10u, 0x110B66u, 0x1220B4u, "Bartender package pickup" },
    { 0x11u, 0x110B5Eu, 0x1220B4u, "Space Needle" },
    { 0x12u, 0x110EFAu, 0x121F70u, "Package delivery" },
    { 0x13u, 0x110EF2u, 0x121F70u, "Package pickup" },
    { 0x14u, 0x111934u, 0x121F70u, "Roscoe the fixer" },
    { 0x15u, 0x11C40Au, 0x121E20u, "Ghoul building" },
    { 0x16u, 0x110F12u, 0x121EECu, "Friendship Restaurant owner" },
    { 0x17u, 0x110F0Au, 0x121EECu, "Friendship Restaurant waitress" },
    { 0x18u, 0x110F02u, 0x121EECu, "Friendship Restaurant" },
    { 0x19u, 0x110D3Eu, 0x121F34u, "Passport Lodge package delivery" },
    { 0x1Au, 0x110D36u, 0x121F34u, "Passport Lodge package pickup" },
    { 0x1Bu, 0x110D46u, 0x121F34u, "Passport Lodge" },
    { 0x1Cu, 0x110F5Eu, 0x122054u, "Ork Embassy package delivery" },
    { 0x1Du, 0x110F56u, 0x122054u, "Ork Embassy package pickup" },
    { 0x1Eu, 0x110F1Au, 0x122054u, "Ork Embassy Building" },
    { 0x1Fu, 0x110C5Eu, 0x121F40u, "Club Penumbra package delivery" },
    { 0x20u, 0x110C42u, 0x121F40u, "Club Penumbra package pickup" },
    { 0x21u, 0x110C7Au, 0x121F40u, "Club Penumbra" },
    { 0x22u, 0x111382u, 0x122090u, "Fuchi package delivery" },
    { 0x23u, 0x11137Au, 0x122090u, "Fuchi package pickup" },
    { 0x24u, 0x110C9Eu, 0x122090u, "Fuchi office entrance" },
    { 0x25u, 0x110BBEu, 0x12209Cu, "Mitsuhama package delivery" },
    { 0x26u, 0x110BA2u, 0x12209Cu, "Mitsuhama package pickup" },
    { 0x27u, 0x110BD2u, 0x12209Cu, "Mitsuhama Downtown office" },
    { 0x28u, 0x110C0Au, 0x122018u, "Eye-Fiver warehouse package delivery" },
    { 0x29u, 0x110BEEu, 0x122018u, "Eye-Fiver warehouse package pickup" },
    { 0x2Au, 0x110C26u, 0x122018u, "Eye-Fiver warehouse" },
    { 0x2Bu, 0x110CE2u, 0x122060u, "The Big Rhino package delivery" },
    { 0x2Cu, 0x110CCEu, 0x122060u, "The Big Rhino package pickup" },
    { 0x2Du, 0x110CC6u, 0x122060u, "The Big Rhino" },
    { 0x2Eu, 0x110F82u, 0x122084u, "Lone Star package delivery" },
    { 0x2Fu, 0x110F7Au, 0x122084u, "Lone Star package pickup" },
    { 0x30u, 0x110F66u, 0x122084u, "Lone Star Security" },
    { 0x31u, 0x111676u, 0x1220C0u, "Ares package delivery" },
    { 0x32u, 0x11166Eu, 0x1220C0u, "Ares package pickup" },
    { 0x33u, 0x110DBEu, 0x1220C0u, "Ares Macrotechnology" },
    { 0x34u, 0x11165Eu, 0x121E50u, "The Wanderer package delivery" },
    { 0x35u, 0x111656u, 0x121E50u, "The Wanderer package pickup" },
    { 0x36u, 0x110DA2u, 0x121E50u, "The Wanderer" },
    { 0x37u, 0x110DB6u, 0x121E50u, "The Wanderer" },
    { 0x38u, 0x110DEEu, 0x122060u, "Underground 93 package delivery" },
    { 0x39u, 0x110DDAu, 0x122060u, "Underground 93 package pickup" },
    { 0x3Au, 0x110E02u, 0x122060u, "Underground 93" },
    { 0x3Bu, 0x110E4Au, 0x122054u, "Ork gang package delivery" },
    { 0x3Cu, 0x110E36u, 0x122054u, "Ork gang package pickup" },
    { 0x3Du, 0x110E5Eu, 0x122054u, "Ork gang hideout" },
    { 0x3Eu, 0x1114A2u, 0x122030u, "Hollywood guard package delivery" },
    { 0x3Fu, 0x11149Au, 0x122030u, "Hollywood guard package pickup" },
    { 0x40u, 0x110D0Au, 0x122030u, "Shiawase Atomics Nuclear Plant" },
    { 0x41u, 0x1114BAu, 0x121EBCu, "Jump House package delivery" },
    { 0x42u, 0x1114B2u, 0x121EBCu, "Jump House package pickup" },
    { 0x43u, 0x110D1Eu, 0x121EBCu, "The Jump House" },
    { 0x44u, 0x1114D2u, 0x121E38u, "Halloweener package delivery" },
    { 0x45u, 0x1114CAu, 0x121E38u, "Halloweener package pickup" },
    { 0x46u, 0x110D26u, 0x121E38u, "The Jackal's Lantern" },
    { 0x47u, 0x1114E2u, 0x122024u, "Elven package delivery" },
    { 0x48u, 0x1114DAu, 0x122024u, "Lone Star grunt" },
    { 0x49u, 0x110D2Eu, 0x122024u, "Lone Star cordon" },
    { 0x4Au, 0x110D72u, 0x121E38u, "Abandoned shack" },
    { 0x4Bu, 0x11155Eu, 0x121E38u, "Halloweener package pickup" },
    { 0x4Cu, 0x110D86u, 0x121E38u, "Abandoned shack" },
    { 0x4Du, 0x1117FAu, 0x121E8Cu, "Frag Grenade package delivery" },
    { 0x4Eu, 0x1117F2u, 0x121E8Cu, "Frag Grenade package pickup" },
    { 0x4Fu, 0x110E96u, 0x121E8Cu, "The Frag Grenade" },
    { 0x50u, 0x1117CEu, 0x121F88u, "Renraku package delivery" },
    { 0x51u, 0x1117B2u, 0x121F88u, "Renraku package pickup" },
    { 0x52u, 0x110E82u, 0x121F88u, "Renraku Computer Systems" },
    { 0x53u, 0x0F4B68u, 0x121E14u, "Tribal council building" },
};

static const size_t shadowrun_dialog_catalog_count =
    sizeof(shadowrun_dialog_catalog) / sizeof(shadowrun_dialog_catalog[0]);

typedef enum {
    SHADOWRUN_DIALOG_ID_CATALOG,
    SHADOWRUN_DIALOG_ID_SCENE_EVENT,
    SHADOWRUN_DIALOG_ID_NODE
} ShadowrunDialogIdKind;

typedef struct {
    int enabled;
    ShadowrunDialogIdKind kind;
    unsigned long id;
} ShadowrunDialogConfig;

static int shadowrun_dialog_config_loaded;
static int shadowrun_dialog_config_attempted;
static ShadowrunDialogConfig shadowrun_dialog_config;
static uint64_t shadowrun_dialog_start_frame = 120u;

static int shadowrun_ini_path(const char *name, char *path, size_t capacity)
{
#ifdef _WIN32
    DWORD length = GetModuleFileNameA(NULL, path, (DWORD)capacity);
    if (length == 0 || length >= capacity) return 0;
    char *separator = strrchr(path, '\\');
    if (!separator) separator = strrchr(path, '/');
    if (!separator) return 0;
    separator[1] = '\0';
    size_t base = strlen(path);
    size_t name_length = strlen(name) + 1u;
    if (base + name_length > capacity) return 0;
    memcpy(path + base, name, name_length);
    return 1;
#else
    (void)name;
    (void)path;
    (void)capacity;
    return 0;
#endif
}

static char *shadowrun_trim(char *text)
{
    while (*text == ' ' || *text == '\t') text++;
    char *end = text + strlen(text);
    while (end > text && (end[-1] == ' ' || end[-1] == '\t' ||
                          end[-1] == '\r' || end[-1] == '\n'))
        *--end = '\0';
    return text;
}

static int shadowrun_parse_bool(const char *value)
{
    return !strcmp(value, "1") || !strcmp(value, "true") ||
           !strcmp(value, "yes") || !strcmp(value, "on");
}

static void shadowrun_parse_dialog_id(const char *value)
{
    char *end = NULL;
    if (value[0] == '0' && (value[1] == 'x' || value[1] == 'X')) {
        const char *digits = value + 2;
        size_t count = strlen(digits);
        unsigned long parsed = strtoul(digits, &end, 16);
        shadowrun_dialog_config.kind = (count <= 2u || count == 4u)
            ? SHADOWRUN_DIALOG_ID_SCENE_EVENT
            : SHADOWRUN_DIALOG_ID_NODE;
        shadowrun_dialog_config.id = parsed;
        return;
    }
    shadowrun_dialog_config.kind = SHADOWRUN_DIALOG_ID_CATALOG;
    shadowrun_dialog_config.id = strtoul(value, &end, 10);
}

static void shadowrun_read_dialog_ini(const char *path)
{
    FILE *file = fopen(path, "rb");
    if (!file) return;

    char line[256];
    while (fgets(line, sizeof(line), file)) {
        char *text = shadowrun_trim(line);
        if (!*text || *text == ';' || *text == '#') continue;
        char *equals = strchr(text, '=');
        if (!equals) continue;
        *equals = '\0';
        char *key = shadowrun_trim(text);
        char *value = shadowrun_trim(equals + 1);
        if (!strcmp(key, "dialog_start")) {
            shadowrun_dialog_config.enabled = shadowrun_parse_bool(value);
        } else if (!strcmp(key, "dialog_id")) {
            shadowrun_parse_dialog_id(value);
        } else if (!strcmp(key, "dialog_start_frame")) {
            shadowrun_dialog_start_frame = (uint64_t)strtoul(value, NULL, 0);
        }
    }
    fclose(file);
}

static void shadowrun_load_dialog_config(void)
{
    if (shadowrun_dialog_config_loaded) return;
    shadowrun_dialog_config_loaded = 1;
    shadowrun_dialog_config.kind = SHADOWRUN_DIALOG_ID_CATALOG;
    shadowrun_dialog_config.id = 0u;

    char path[512];
    if (shadowrun_ini_path("settings.ini", path, sizeof(path)))
        shadowrun_read_dialog_ini(path);
    if (shadowrun_ini_path("debug.ini", path, sizeof(path)))
        shadowrun_read_dialog_ini(path);
}

static void shadowrun_call_guest(uint32_t address, uint32_t a0_value, uint32_t a5_value)
{
    uint32_t saved_a7 = g_cpu.A[7];
    g_cpu.A[7] -= 4;
    m68k_write32(g_cpu.A[7], 0x000D42u);
    g_cpu.A[0] = a0_value;
    g_cpu.A[5] = a5_value;
    g_cpu.A[1] = 0;
    recomp_call_addr(address);
    g_cpu.A[7] = saved_a7;
}

static void shadowrun_prepare_samurai(void)
{
    for (uint32_t offset = 0; offset < 0x100u; offset++)
        m68k_write8(0x00FF0100u + offset, m68k_read8(0x0007291Au + offset));
    m68k_write8(0x00FF019Bu, 0x02u);
    m68k_write32(0x00FFFC04u, 0x00FF0100u);
    m68k_write32(0x00FF0150u, m68k_read32(0x0007291Au + 0x50u));
    m68k_write8(0x00FF0110u, (uint8_t)(m68k_read8(0x00FF0110u) | 0x02u));
    m68k_write8(0x00FF0210u, (uint8_t)(m68k_read8(0x00FF0210u) & 0xFDu));
    m68k_write8(0x00FF0310u, (uint8_t)(m68k_read8(0x00FF0310u) & 0xFDu));
}

static const ShadowrunDialogEntry *shadowrun_find_dialog_by_node(uint32_t node)
{
    for (size_t index = 0; index < shadowrun_dialog_catalog_count; index++) {
        if (shadowrun_dialog_catalog[index].node == node)
            return &shadowrun_dialog_catalog[index];
    }
    return NULL;
}

static void shadowrun_start_dialog_at_node(uint32_t node, uint32_t actor)
{
    m68k_write8(0x00FFF0D5u, 0x00u);
    m68k_write8(0x00FFF0D6u, 0x00u);
    fprintf(stderr, "[dialog] start node=$%06X actor=$%06X frame=%llu\n",
            (unsigned)node, (unsigned)actor, (unsigned long long)g_frame_count);
    shadowrun_call_guest(0x01F246u, node, actor);
}

static void shadowrun_start_dialog(void)
{
    shadowrun_prepare_samurai();
    if (shadowrun_dialog_config.kind == SHADOWRUN_DIALOG_ID_SCENE_EVENT) {
        uint8_t scene = (uint8_t)(shadowrun_dialog_config.id >> 8);
        uint8_t event = (uint8_t)(shadowrun_dialog_config.id & 0xFFu);
        fprintf(stderr, "[dialog] start scene=%u event=%u frame=%llu\n",
                (unsigned)scene, (unsigned)event, (unsigned long long)g_frame_count);
        m68k_write8(0x00FFFBF8u, scene);
        m68k_write8(0x00FFFBF9u, event);
        m68k_write8(0x00FFF0D5u, 0x00u);
        m68k_write8(0x00FFF0D6u, 0x00u);
        shadowrun_call_guest(0x01FD80u, 0, 0);
        return;
    }
    if (shadowrun_dialog_config.kind == SHADOWRUN_DIALOG_ID_NODE) {
        const ShadowrunDialogEntry *entry =
            shadowrun_find_dialog_by_node((uint32_t)shadowrun_dialog_config.id);
        uint32_t actor = entry ? entry->actor : 0x00122030u;
        shadowrun_start_dialog_at_node((uint32_t)shadowrun_dialog_config.id, actor);
        return;
    }
    if (shadowrun_dialog_config.id >= shadowrun_dialog_catalog_count) {
        fprintf(stderr, "[dialog] id %lu is outside the catalog (0..%u)\n",
                shadowrun_dialog_config.id, (unsigned)(shadowrun_dialog_catalog_count - 1));
        return;
    }
    const ShadowrunDialogEntry *entry =
        &shadowrun_dialog_catalog[shadowrun_dialog_config.id];
    fprintf(stderr, "[dialog] id=%u %s\n", entry->id, entry->name);
    shadowrun_start_dialog_at_node(entry->node, entry->actor);
}

void shadowrun_dialogs_maybe_start(void)
{
    if (shadowrun_dialog_config_attempted) return;
    shadowrun_load_dialog_config();
    if (!shadowrun_dialog_config.enabled) {
        shadowrun_dialog_config_attempted = 1;
        return;
    }
    if (g_frame_count < shadowrun_dialog_start_frame) return;
    shadowrun_dialog_config_attempted = 1;
    shadowrun_start_dialog();
}
