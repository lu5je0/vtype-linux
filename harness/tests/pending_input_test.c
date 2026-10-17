/* 用假 JNI 的真实字段路径验证原始按键重建，不需要 APK 或个人词库。 */
#define main wetype_harness_main
#include "../jinterop.c"
#undef main

static void check(int condition, const char *message) {
    if (!condition) { fprintf(stderr, "失败：%s\n", message); exit(1); }
}

static JObj *node(const char *kind, const char *field, const char *text) {
    char cls[128];
    snprintf(cls, sizeof cls, "com/tencent/wxhld/info/%s", kind);
    JObj *o = obj_new(strdup(cls));
    if (field) {
        JIDToken id = {.name = field};
        F_SetObjectField(NULL, o, &id, str_obj(text));
    }
    return o;
}

static void expect(void **items, int count, const char *input, int known) {
    JArr a = {.elem = items, .len = count};
    JIDToken id = {.name = "pendingInputs"};
    JObj *pending = obj_new("com/tencent/wxhld/info/PendingInputV2");
    F_SetObjectField(NULL, pending, &id, &a);
    check(g_pi_have == known, "输入完整性标记错误");
    if (known) check(!strcmp(g_pi_last, input), "没有还原用户原始按键");
}

int main(void) {
    g_verbose = 0;
    g_daemon_mode = 1;
    /* jjj 的中间字母是删除纠错，仍必须归属本次输入。 */
    void *deleted[] = {node("PendingExactlyMatch", "match", "j"),
                       node("PendingDeletion", "deleted", "j"),
                       node("PendingExactlyMatch", "match", "j")};
    expect(deleted, 3, "jjj", 1);
    /* 键邻纠错取 from，不应漏字，也不应把纠正后的 to 加进去。 */
    JObj *replacement = node("PendingReplacement", "from", "j");
    obj_set(replacement, "to", 's', "i");
    void *replaced[] = {deleted[0], replacement, deleted[2], replacement, deleted[0]};
    expect(replaced, 5, "jjjjj", 1);
    /* nihoa 的交换记录只贡献 left=o；right=a 已由后续 match=a 表示。 */
    JObj *exchange = node("PendingExchange", "left", "o");
    obj_set(exchange, "right", 's', "a");
    void *swapped[] = {node("PendingExactlyMatch", "match", "nih"), exchange,
                       node("PendingExactlyMatch", "match", "a")};
    expect(swapped, 3, "nihoa", 1);
    /* 纠错插入、自动分隔、已选中文和光标均不能变成新的原始字母。 */
    void *inserted[] = {node("PendingSelectedText", "text", "你好"),
                        node("PendingExactlyMatch", "match", "n"),
                        node("PendingInsertion", "inserted", "i"),
                        node("PendingSeparator", NULL, NULL),
                        node("PendingExactlyMatch", "match", "hao"),
                        node("PendingInternalCursor", NULL, NULL)};
    expect(inserted, 6, "nhao", 1);
    /* 数组顺序才是输入顺序，字段构造顺序和上一次回调不得混入。 */
    void *reverse[] = {swapped[2], swapped[0]};
    expect(reverse, 2, "anih", 1);
    expect(NULL, 0, "", 1);
    /* 前端保留原始大小写，不能把英文混输标记为未知而等满超时。 */
    void *mixed[] = {node("PendingExactlyMatch", "match", "Bev"),
                     node("PendingExactlyMatch", "match", "Fusion")};
    expect(mixed, 2, "BevFusion", 1);
    void *uppercase[] = {node("PendingExactlyMatch", "match", "ABC")};
    expect(uppercase, 1, "ABC", 1);
    /* 无法还原时保持未知，不能让部分字符串冒充精确命中。 */
    void *unknown[] = {deleted[0], node("PendingFutureType", "match", "j")};
    expect(unknown, 2, NULL, 0);
    void *missing[] = {node("PendingReplacement", "to", "i")};
    expect(missing, 1, NULL, 0);
    void *invalid[] = {node("PendingExactlyMatch", "match", "ni3")};
    expect(invalid, 1, NULL, 0);
    char long_input[257]; memset(long_input, 'j', 256); long_input[255] = 0;
    void *long_node[] = {node("PendingExactlyMatch", "match", long_input)};
    expect(long_node, 1, long_input, 1);
    long_input[255] = 'j'; long_input[256] = 0;
    long_node[0] = node("PendingExactlyMatch", "match", long_input);
    expect(long_node, 1, NULL, 0);
    pending_input_field("pendingInputs", NULL);
    check(!g_pi_have, "空数组指针被误认为完整输入");
    /* 候选 iterator 绑定的是完整快照，之后另一个数组不能改写已绑定输入。 */
    expect(deleted, 3, "jjj", 1);
    JObj *candidate = obj_new("com/tencent/wxhld/info/CandidateList");
    JIDToken iterator = {.name = "newIterator"};
    F_SetLongField(NULL, candidate, &iterator, 1);
    expect(swapped, 3, "nihoa", 1);
    check(g_pend_known && !strcmp(g_pend_input, "jjj"), "候选与输入快照绑定错误");
    puts("原始按键重建检查通过");
    return 0;
}
