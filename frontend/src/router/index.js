import { createRouter, createWebHistory } from "vue-router";
import AccountView from "../views/AccountView.vue";
import ChatView from "../views/ChatView.vue";
import DocumentsView from "../views/DocumentsView.vue";
import MapView from "../views/MapView.vue";
import PlansView from "../views/PlansView.vue";
import PasswordView from "../views/PasswordView.vue";
import ProfileView from "../views/ProfileView.vue";
import RegisterView from "../views/RegisterView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/chat" },
    { path: "/chat", name: "chat", component: ChatView, meta: { title: "对话" } },
    { path: "/account", name: "account", component: AccountView, meta: { title: "登录", showTabBar: false } },
    { path: "/register", name: "register", component: RegisterView, meta: { title: "注册", showTabBar: false } },
    { path: "/profile", name: "profile", component: ProfileView, meta: { title: "个人资料", showTabBar: false } },
    { path: "/password", name: "password", component: PasswordView, meta: { title: "安全设置", showTabBar: false } },
    { path: "/documents", name: "documents", component: DocumentsView, meta: { title: "文档中心" } },
    { path: "/map", name: "map", component: MapView, meta: { title: "导航" } },
    { path: "/plans", name: "plans", component: PlansView, meta: { title: "计划" } },
    { path: "/:pathMatch(.*)*", redirect: "/chat" },
  ],
});

router.afterEach((to) => {
  document.title = `${to.meta.title || "助手"} - Agent`;
});

export default router;
