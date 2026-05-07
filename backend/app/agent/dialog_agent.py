"""
Dialog Agent 核心实现
只负责理解当前问题、结合 Memory Agent 提供的记忆上下文进行推理，并生成最终回复
不负责记忆管理、压缩、总结、裁剪历史消息
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from llm.llm import read_llm
from project_config import SETTINGS

from .models import ModuleName
from .skill_loader import load_skill_metadata, read_reference
from .tools import build_default_tools


class DialogAgent:
    """Dialog Agent - 专门负责对话生成"""

    def __init__(self, skill_path: str | Path) -> None:
        self.skill = load_skill_metadata(skill_path)
        self.skill_text = Path(skill_path).read_text(encoding="utf-8")
        self._agents: dict[tuple[int | None, int | None], Any] = {}

    async def _get_agent(self, user_id: int | None = None, top_k: int | None = None) -> Any:
        """获取绑定工具的 Agent 实例"""
        cache_key = (user_id, top_k)
        agent = self._agents.get(cache_key)
        if agent is None:
            read_llm()
            llm = ChatOpenAI(model=SETTINGS.llm_model, temperature=0.2)
            tools = await build_default_tools(user_id=user_id, top_k=top_k)
            agent = create_agent(model=llm, tools=tools)
            self._agents[cache_key] = agent
        return agent

    async def prepare_tool_agents(self, user_id: int | None = None, top_k: int | None = None) -> None:
        await self._get_agent(user_id=user_id, top_k=top_k)

    def _build_poi_instruction(self, poi_data: list[dict[str, Any]]) -> str:
        """构建基于 POI 数据的生成指令"""
        instruction_parts = [
            "工具已返回以下 POI 数据，每个 POI 都有唯一 ID，名称、地址、图片已通过 ID 严格绑定。",
            "请严格基于这些数据生成推荐，必须遵守以下规则：",
            "",
            "【强制规则 - 违反将导致输出无效】",
            "1. 【数量要求】必须输出 3-5 个 POI",
            "   - 如果数据有 8 个以上，必须选择其中 3-5 个",
            "   - 如果数据有 3-7 个，必须输出 3-5 个",
            "   - 如果数据少于 3 个，输出所有可用的并说明'当前仅找到 X 个'",
            "   - 禁止只输出 1-2 个就停止",
            "",
            "2. 【名称匹配】每个 POI 的名称必须与下方数据中的 name 字段完全一致",
            "   - 必须逐字复制，包括所有字符、空格、括号、标点",
            "   - 禁止任何修改、简化、泛化或改写",
            "   - 示例：'如家酒店(北京王府井店)' 不能改为 '如家酒店' 或 '如家王府井店'",
            "",
            "3. 【图片匹配】每个 POI 的图片必须使用该 POI 对应的 photo 字段",
            "   - 通过 POI_ID 确保名称和图片来自同一条数据",
            "   - 禁止将 POI_1 的图片用于 POI_2",
            "   - 如果某个 POI 没有 photo 字段，则不输出图片行",
            "",
            "4. 【输出格式】图片格式必须为：图片：![POI名称](photo_url)",
            "",
            "【POI 数据 - 每个 POI 都有唯一 ID 标识】",
        ]

        for i, poi in enumerate(poi_data[:8], 1):
            poi_id = f"POI_{i}"
            instruction_parts.append(f"\n{poi_id}:")
            instruction_parts.append(f"  id: {poi_id}")
            instruction_parts.append(f"  name: {poi['name']}")
            if poi.get('address'):
                instruction_parts.append(f"  address: {poi['address']}")
            if poi.get('photos') and len(poi['photos']) > 0:
                instruction_parts.append(f"  photo: {poi['photos'][0]}")
            if poi.get('type'):
                instruction_parts.append(f"  type: {poi['type']}")

        instruction_parts.extend([
            "",
            "【输出要求 - 严格执行】",
            "1. 从上述 POI 中选择 3-5 个进行推荐（强制数量要求）",
            "2. 每个推荐必须包含：",
            "   - 名称：完全复制对应 POI 的 name 字段（逐字复制）",
            "   - 地址：使用对应 POI 的 address 字段",
            "   - 推荐原因：你可以自己编写",
            "   - 图片：使用对应 POI 的 photo 字段，格式：图片：![name](photo)",
            "3. 确保每个推荐的名称和图片来自同一个 POI_ID",
            "4. 按照 skill 要求的格式输出",
            "5. 不要输出不在上述列表中的 POI",
            "",
            "【示例输出格式】",
            "假设选择了 POI_1 和 POI_2：",
            "",
            "酒店1",
            f"酒店名称：{poi_data[0]['name'] if poi_data else '[POI_1的name字段]'}",
            f"地址：{poi_data[0].get('address', '[POI_1的address字段]') if poi_data else '[POI_1的address字段]'}",
            "适合：[你编写的适合人群]",
            "推荐原因：[你编写的推荐原因]",
            f"图片：![{poi_data[0]['name']}]({poi_data[0]['photos'][0]})" if poi_data and poi_data[0].get('photos') else "图片：![POI_1的name](POI_1的photo)",
        ])

        return "\n".join(instruction_parts)

    def _extract_json_values_from_text(self, content: str) -> list[Any]:
        values: list[Any] = []
        decoder = json.JSONDecoder()
        index = 0
        while index < len(content):
            match = re.search(r"[\[{]", content[index:])
            if not match:
                break
            start = index + match.start()
            try:
                value, end = decoder.raw_decode(content[start:])
            except json.JSONDecodeError:
                index = start + 1
                continue
            values.append(value)
            index = start + end
        return values

    def _decode_tool_payloads(self, content: Any) -> list[Any]:
        if isinstance(content, (dict, list)):
            if isinstance(content, list):
                values: list[Any] = []
                for item in content:
                    values.extend(self._decode_tool_payloads(item))
                return values
            text_value = content.get("text")
            if isinstance(text_value, str):
                parsed_text_values = self._decode_tool_payloads(text_value)
                if parsed_text_values:
                    return parsed_text_values
            return [content]

        if not isinstance(content, str):
            return []

        text = content.strip()
        if not text:
            return []

        try:
            return [json.loads(text)]
        except (json.JSONDecodeError, ValueError):
            values = self._extract_json_values_from_text(text)
            if values:
                print(f"[DEBUG] 从混合文本中提取到 {len(values)} 个 JSON 片段")
            return values

    def _collect_poi_candidates(self, data: Any) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("name"):
                    candidates.append(item)
                else:
                    candidates.extend(self._collect_poi_candidates(item))
            return candidates

        if not isinstance(data, dict):
            return candidates

        if data.get("name"):
            candidates.append(data)

        for key in ("pois", "results", "data", "list", "items", "places", "hotels", "restaurants"):
            value = data.get(key)
            if isinstance(value, (list, dict)):
                candidates.extend(self._collect_poi_candidates(value))

        return candidates

    def _extract_poi_data_from_tools(self, messages: list[Any]) -> list[dict[str, Any]]:
        """从工具调用结果中提取完整的 POI 数据（名称、地址、图片已绑定，添加唯一 ID）"""
        poi_list: list[dict[str, Any]] = []
        poi_id_counter = 1
        seen_names: set[str] = set()

        print(f"[DEBUG] 开始提取POI，消息数量: {len(messages)}")

        for msg in messages:
            msg_type = getattr(msg, "type", "")
            print(f"[DEBUG] 消息类型: {msg_type}")

            if msg_type != "tool":
                continue

            content = getattr(msg, "content", "")

            # 处理content可能是列表的情况（MCP工具返回）
            if isinstance(content, list):
                print(f"[DEBUG] 内容是列表，长度: {len(content)}")

            if not isinstance(content, str):
                print(f"[DEBUG] 内容不是字符串: {type(content)}")
            else:
                print(f"[DEBUG] 工具返回内容长度: {len(content)}")

            payloads = self._decode_tool_payloads(content)
            if not payloads:
                print("[DEBUG] 未能从工具结果中解析出可用JSON")
                continue

            pois: list[Any] = []
            for data in payloads:
                extracted = self._collect_poi_candidates(data)
                if extracted:
                    print(f"[DEBUG] 从payload提取到POI候选，数量: {len(extracted)}")
                    pois.extend(extracted)

            for poi in pois:
                if not isinstance(poi, dict):
                    continue

                name = str(poi.get("name", "")).strip()
                if not name:
                    continue
                if name in seen_names:
                    continue
                seen_names.add(name)

                # 提取地址
                address = str(poi.get("address", "") or poi.get("location", "") or "").strip()

                # 提取图片 - 高德返回的是photo字段（单个URL字符串）
                photos = poi.get("photos", [])
                photo_field = poi.get("photo", "")  # 高德MCP返回的是photo字段

                if not photos and photo_field:
                    # 如果photos为空但photo字段有值，使用photo字段
                    photos = [photo_field]

                if not photos:
                    for photo_key in ("images", "pictures", "image", "pic", "pics"):
                        if poi.get(photo_key):
                            photos = poi[photo_key]
                            if not isinstance(photos, list):
                                photos = [photos]
                            break

                photo_urls: list[str] = []
                for photo in photos:
                    if isinstance(photo, dict):
                        url = str(photo.get("url", "") or photo.get("src", "") or photo.get("link", "") or photo.get("href", "")).strip()
                    else:
                        url = str(photo).strip()
                    if url.startswith("http"):
                        photo_urls.append(url)

                # 构建 POI 数据对象，添加唯一 ID 标识
                poi_data = {
                    "poi_id": f"POI_{poi_id_counter}",
                    "name": name,
                    "address": address,
                    "photos": photo_urls,
                }

                # 提取其他可能有用的字段
                for field in ("type", "typecode", "rating", "price", "tags", "description", "location"):
                    if field in poi:
                        poi_data[field] = poi[field]

                # 解析 location 坐标为 lng/lat
                location = str(poi.get("location", "")).strip()
                if location and "," in location:
                    parts = location.split(",")
                    try:
                        poi_data["lng"] = float(parts[0].strip())
                        poi_data["lat"] = float(parts[1].strip())
                    except (ValueError, TypeError):
                        pass

                poi_list.append(poi_data)
                poi_id_counter += 1

                print(f"[DEBUG] 提取 POI: {poi_data['poi_id']} -> 名称: {name}, 图片数: {len(photo_urls)}")

        print(f"[DEBUG] 总共提取到 {len(poi_list)} 个 POI 数据")
        return poi_list

    def _format_poi_context(self, poi_list: list[dict[str, Any]]) -> str:
        """将 POI 数据格式化为上下文字符串"""
        lines = []
        for i, poi in enumerate(poi_list, 1):
            lines.append(f"POI {i}:")
            lines.append(f"  名称: {poi['name']}")
            if poi.get('address'):
                lines.append(f"  地址: {poi['address']}")
            if poi.get('photos'):
                lines.append(f"  图片: {poi['photos'][0]}")  # 使用第一张图片
            if poi.get('type'):
                lines.append(f"  类型: {poi['type']}")
            lines.append("")
        return "\n".join(lines)

    def _is_hotel_request(self, user_input: str) -> bool:
        text = user_input.lower()
        return any(term in text for term in ("hotel", "homestay", "\u9152\u5e97", "\u4f4f\u5bbf", "\u6c11\u5bbf", "\u4f4f\u54ea"))

    def _is_restaurant_request(self, user_input: str) -> bool:
        text = user_input.lower()
        return any(term in text for term in ("restaurant", "food", "dining", "\u9910\u5385", "\u9910\u9986", "\u7f8e\u98df", "\u5403\u54ea", "\u5403\u4ec0\u4e48", "\u5403\u996d"))

    def _is_travel_plan_request(self, user_input: str) -> bool:
        text = user_input.lower()
        return any(
            term in text
            for term in (
                "itinerary",
                "travel plan",
                "trip plan",
                "\u884c\u7a0b",
                "\u653b\u7565",
                "\u65c5\u6e38",
                "\u65c5\u884c",
                "\u51fa\u884c",
                "\u51fa\u884c\u8ba1\u5212",
                "\u6e38\u73a9",
                "\u666f\u70b9",
                "\u73a9",
                "\u8def\u7ebf",
                "\u5b89\u6392",
                "\u51e0\u5929",
                "\u4e00\u65e5\u6e38",
                "\u4e24\u65e5\u6e38",
                "\u4e09\u65e5\u6e38",
            )
        )

    def _needs_itinerary_transport_repair(self, current_input: str, content: str) -> bool:
        if not self._is_travel_plan_request(current_input):
            return False
        if not re.search(r"第\s*[一二三四五六七八九十\d]+\s*天", content) and not re.search(r"\b(?:D|Day)\s*\d+\b", content, re.IGNORECASE):
            return False
        transport_markers = (
            "\u666f\u70b9\u95f4\u4ea4\u901a",
            "\u4e0a\u5348\u666f\u70b9\u95f4\u4ea4\u901a",
            "\u5348\u9910\u540e\u4ea4\u901a",
            "\u4e0b\u5348\u666f\u70b9\u95f4\u4ea4\u901a",
            "\u665a\u95f4\u8fd4\u56de\u4ea4\u901a",
        )
        if any(marker in content for marker in transport_markers):
            return False
        concrete_methods = ("\u5730\u94c1", "\u516c\u4ea4", "\u6b65\u884c", "\u6253\u8f66", "\u51fa\u79df\u8f66", "\u81ea\u9a7e", "\u9a91\u884c", "\u6446\u6e21", "\u6362\u4e58")
        link_keywords = ("\u666f\u70b9\u95f4", "\u4e0a\u5348\u666f\u70b9", "\u5348\u9910\u540e", "\u4e0b\u5348\u666f\u70b9", "\u665a\u95f4\u8fd4\u56de", "\u4ece", "\u5230")
        has_transport_line = any(
            "\u4ea4\u901a" in line
            and any(method in line for method in concrete_methods)
            and any(keyword in line for keyword in link_keywords)
            for line in content.splitlines()
        )
        return not has_transport_line

    def _ensure_itinerary_transport_fallback(self, current_input: str, content: str) -> str:
        if not self._needs_itinerary_transport_repair(current_input, content):
            return content

        lines = content.splitlines()
        repaired: list[str] = []
        current_day = ""
        inserted_for_day: set[str] = set()
        day_pattern = re.compile(r"第\s*[一二三四五六七八九十\d]+\s*天")

        def add_once(key: str, text: str) -> None:
            marker = f"{current_day}:{key}"
            if current_day and marker not in inserted_for_day:
                repaired.append(text)
                inserted_for_day.add(marker)

        for line in lines:
            stripped = line.strip()
            if day_pattern.search(stripped) or re.search(r"\b(?:D|Day)\s*\d+\b", stripped, re.IGNORECASE):
                current_day = stripped
                inserted_for_day = set()

            repaired.append(line)

            if not current_day:
                continue

            if "\u4e0a\u5348" in stripped and "\u4ea4\u901a" not in stripped:
                add_once("morning", "\U0001F687 \u4e0a\u5348\u666f\u70b9\u95f4\u4ea4\u901a\uff1a\u6309\u666f\u70b9\u8ddd\u79bb\u4f18\u5148\u6b65\u884c\u6216\u5730\u94c1\uff0c\u8de8\u533a\u666f\u70b9\u5efa\u8bae\u5730\u94c1\u6216\u6253\u8f66\uff0c\u5355\u6bb5\u7ea6 15-35 \u5206\u949f\u3002")
            elif "\u5348\u9910" in stripped and "\u4ea4\u901a" not in stripped:
                add_once("lunch", "\U0001F687 \u5348\u9910\u540e\u4ea4\u901a\uff1a\u4ece\u5348\u9910\u70b9\u5230\u4e0b\u5348\u666f\u70b9\u5efa\u8bae\u5c31\u8fd1\u6b65\u884c\uff0c\u8ddd\u79bb\u8f83\u8fdc\u65f6\u7528\u5730\u94c1\u6216\u6253\u8f66\uff0c\u7ea6 15-30 \u5206\u949f\u3002")
            elif "\u4e0b\u5348" in stripped and "\u4ea4\u901a" not in stripped:
                add_once("afternoon", "\U0001F687 \u4e0b\u5348\u666f\u70b9\u95f4\u4ea4\u901a\uff1a\u4e0b\u5348\u5404\u666f\u70b9\u95f4\u4f18\u5148\u5730\u94c1\u6216\u6253\u8f66\u8854\u63a5\uff0c\u5e02\u533a\u77ed\u8ddd\u79bb\u53ef\u6b65\u884c\uff0c\u5355\u6bb5\u7ea6 20-40 \u5206\u949f\u3002")
            elif ("\u665a\u95f4" in stripped or "\u591c\u95f4" in stripped) and "\u4ea4\u901a" not in stripped:
                add_once("evening", "\U0001F687 \u665a\u95f4\u8fd4\u56de\u4ea4\u901a\uff1a\u4ece\u665a\u95f4\u6d3b\u52a8\u70b9\u8fd4\u56de\u4f4f\u5bbf\u533a\u5efa\u8bae\u5730\u94c1\u6216\u6253\u8f66\uff0c\u665a\u9ad8\u5cf0\u9884\u7559\u7ea6 20-45 \u5206\u949f\u3002")

        return "\n".join(repaired).strip()

    def _ensure_required_expressions(self, content: str) -> str:
        text = str(content or "").strip()
        if not text:
            return text

        text = re.sub(r"[\(\uff08][^\n\)\uff09]*[\u8059\u8292\u6c13\u76f2\u732b][^\n\)\uff09]*[\)\uff09]", "", text).strip()
        text = re.sub(r"[\s\u8059\u8079\u8292\u6c13\u76f2\u732b\u6402]+$", "", text).strip()
        emoji_pattern = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]")
        kaomoji_pattern = re.compile(r"[\(\uff08][^\n]{0,20}[•\u25e1\u25bd\u30fb\u1d17\u03c9\u30ee\u2570\u256f\u0e07][^\n]{0,20}[\)\uff09]")

        has_emoji = bool(emoji_pattern.search(text))
        has_kaomoji = bool(kaomoji_pattern.search(text))

        prefix_parts: list[str] = []
        if not has_emoji:
            prefix_parts.append("\u2705")
        if not has_kaomoji:
            prefix_parts.append("(\u256f\u25bd\u2570)")

        if not prefix_parts:
            return text
        return f"{' '.join(prefix_parts)} {text}"

    async def _repair_itinerary_transport(
        self,
        agent: Any,
        base_messages: list[Any],
        current_input: str,
        content: str,
    ) -> str:
        repair_messages = list(base_messages)
        repair_messages.append({"role": "assistant", "content": content})
        repair_messages.append(
            {
                "role": "system",
                "content": (
                    "上一次行程输出缺少景点之间的交通衔接，必须完整重写最终回答。\n"
                    "保持原有目的地、天数、景点、餐饮、住宿建议，不要改成只补充说明。\n"
                    "每个包含 2 个及以上景点的日期块必须加入这些字段：\n"
                    "🚇 上午景点间交通：从 A 到 B，推荐方式，约耗时，换乘或步行提示\n"
                    "🚇 午餐后交通：从午餐点或上午最后景点到下午景点，推荐方式，约耗时\n"
                    "🚇 下午景点间交通：从 C 到 D，推荐方式，约耗时，换乘或步行提示\n"
                    "🚇 晚间返回交通：从晚间活动点到住宿区域或交通枢纽，推荐方式，约耗时\n"
                    "如果没有实时路线数据，也要用保守估算写出地铁、公交、步行、打车或自驾等明确方式。\n"
                    "禁止只写“交通方便”“前往下一站”。禁止使用 Markdown 列表符号。"
                ),
            }
        )
        repair_messages.append(
            {
                "role": "system",
                "content": (
                    "Rewrite the full itinerary because the previous answer missed transport links between attractions. "
                    "Do not only append a note. Keep the original days, attractions, meals, and stay suggestions, but add explicit route-transfer lines inside each day block. "
                    "For any day with two or more attractions, include concrete transport method, origin, destination, approximate duration, and transfer or walking note. "
                    "Use metro, bus, walking, taxi, self-driving, cycling, ferry, or shuttle when appropriate. "
                    "Use these Chinese labels exactly when applicable: "
                    "\u4e0a\u5348\u666f\u70b9\u95f4\u4ea4\u901a, "
                    "\u5348\u9910\u540e\u4ea4\u901a, "
                    "\u4e0b\u5348\u666f\u70b9\u95f4\u4ea4\u901a, "
                    "\u665a\u95f4\u8fd4\u56de\u4ea4\u901a. "
                    "Never write vague phrases like transport is convenient or go to the next stop without a method. "
                    "Do not use Markdown bullet symbols."
                ),
            }
        )
        repair_messages.append({"role": "user", "content": current_input})
        response = await agent.ainvoke({"messages": repair_messages})
        all_messages = response.get("messages", []) if isinstance(response, dict) else []
        if not all_messages:
            return content
        repaired = str(getattr(all_messages[-1], "content", all_messages[-1])).strip()
        return repaired or content

    def _poi_matches_kind(self, poi: dict[str, Any], kind: str) -> bool:
        text = " ".join(str(poi.get(field, "")) for field in ("name", "type", "tags", "description")).lower()
        if kind == "hotel":
            return any(term in text for term in ("hotel", "\u9152\u5e97", "\u5bbe\u9986", "\u65c5\u9986", "\u4f4f\u5bbf", "\u6c11\u5bbf", "\u5ba2\u6808"))
        if kind == "restaurant":
            return any(term in text for term in ("restaurant", "food", "\u9910\u5385", "\u9910\u996e", "\u7f8e\u98df", "\u996d\u5e97", "\u706b\u9505", "\u5c0f\u5403", "\u9762\u9986", "\u8336\u9910\u5385"))
        return True

    def _select_poi_candidates(self, poi_data: list[dict[str, Any]], kind: str, limit: int = 5) -> list[dict[str, Any]]:
        seen: set[str] = set()
        matched: list[dict[str, Any]] = []
        for poi in poi_data:
            name = str(poi.get("name", "")).strip()
            if not name or name in seen:
                continue
            if self._poi_matches_kind(poi, kind):
                matched.append(poi)
                seen.add(name)
            if len(matched) >= limit:
                break
        return matched

    def _format_recommendation_item(self, poi: dict[str, Any], kind: str, index: int) -> list[str]:
        is_hotel = kind == "hotel"
        item_label = "\u9152\u5e97" if is_hotel else "\u9910\u5385"
        name_label = "\u9152\u5e97\u540d\u79f0" if is_hotel else "\u9910\u5385\u540d\u79f0"
        name = str(poi.get("name", "")).strip()
        address = str(poi.get("address", "")).strip()
        poi_type = str(poi.get("type", "")).strip()
        lines = [f"{item_label}{index}", f"{name_label}\uff1a{name}"]
        if address:
            lines.append(f"\u5730\u5740\uff1a{address}")
        if poi_type and not is_hotel:
            lines.append(f"\u7c7b\u578b\uff1a{poi_type}")
        if is_hotel:
            lines.append("\u63a8\u8350\u539f\u56e0\uff1a\u4f4d\u7f6e\u548c\u5468\u8fb9\u914d\u5957\u8f83\u6e05\u6670\uff0c\u9002\u5408\u4f5c\u4e3a\u884c\u7a0b\u4f4f\u5bbf\u5019\u9009\u3002")
        else:
            lines.append("\u63a8\u8350\u539f\u56e0\uff1a\u4fe1\u606f\u5339\u914d\u5f53\u524d\u533a\u57df\u9700\u6c42\uff0c\u9002\u5408\u4f5c\u4e3a\u5c31\u8fd1\u7528\u9910\u5019\u9009\u3002")
        photos = poi.get("photos", [])
        if photos:
            lines.append(f"\u56fe\u7247\uff1a![{name}]({photos[0]})")
        return lines

    def _build_deterministic_poi_response(self, current_input: str, poi_data: list[dict[str, Any]]) -> str | None:
        if not poi_data:
            return None

        wants_hotel = self._is_hotel_request(current_input)
        wants_restaurant = self._is_restaurant_request(current_input)
        if not wants_hotel and not wants_restaurant:
            return None

        sections: list[str] = []
        requested: list[tuple[str, str]] = []
        if wants_hotel:
            requested.append(("hotel", "\U0001F3E8 \u4f4f\u5bbf\u63a8\u8350"))
        if wants_restaurant:
            requested.append(("restaurant", "\U0001F37D \u9910\u996e\u63a8\u8350"))

        for kind, title in requested:
            candidates = self._select_poi_candidates(poi_data, kind)
            if not candidates:
                continue

            sections.append(title)
            if len(candidates) < 3:
                label = "\u9152\u5e97" if kind == "hotel" else "\u9910\u5385"
                sections.append(f"\u5f53\u524d\u4ec5\u627e\u5230 {len(candidates)} \u4e2a\u53ef\u9760{label}\u5019\u9009")

            for index, poi in enumerate(candidates[:5], 1):
                sections.extend(self._format_recommendation_item(poi, kind, index))
                sections.append("")

        return "\n".join(line for line in sections if line is not None).strip() or None

    def _select_reference_module(self, current_input: str, memory_context: dict[str, Any]) -> ModuleName:
        text_parts = [current_input]
        for message in memory_context.get("recent_full_memory", [])[-4:]:
            text_parts.append(str(message.get("content", "")))
        text = "\n".join(text_parts).lower()
        current = current_input.strip().lower()

        low_info = {"hi", "hello", "thanks", "thank you", "ok", "嗯", "好的", "谢谢", "你好", "在吗", "继续", "然后呢"}
        if current in low_info or len(current_input.strip()) <= 3:
            return "general_chat"
        if any(word in text for word in ("车票", "火车", "高铁", "动车", "12306", "车次", "余票", "票价", "座位")):
            return "ticket_service"
        if any(word in text for word in ("酒店", "民宿", "住宿", "住哪", "餐厅", "吃饭", "美食", "附近吃", "附近住")):
            return "hotel_restaurant"
        if any(word in text for word in ("规则", "政策", "流程", "怎么办理", "规定", "说明", "为什么")):
            return "rag"
        if any(word in text for word in ("旅游", "旅行", "行程", "攻略", "景点", "路线", "怎么玩", "几天", "一日游", "日游", "游玩")):
            return "travel_planning"
        return "general_chat"

    def _build_system_prompt(self, memory_context: dict[str, Any], current_input: str) -> str:
        """构建系统提示词 - 基于分层记忆"""
        module = self._select_reference_module(current_input, memory_context)
        reference_blob = read_reference(self.skill.references[module])

        # 构建记忆上下文文本
        memory_text_parts = []

        # 1. 长期摘要（如果存在）
        memory_text_parts = []

        retrieved_long_term = memory_context.get("retrieved_long_term_memory", [])
        if retrieved_long_term:
            memory_text_parts.append("=== Retrieved Long-Term Markdown Memory ===")
            for item in retrieved_long_term:
                memory_text_parts.append(f"Source: {item['file']} > {item['section']}")
                memory_text_parts.append(item["content"])
            memory_text_parts.append("")

        session_summary = memory_context.get("session_summary")
        if session_summary:
            memory_text_parts.append("=== Short-Term Session Summary ===")
            memory_text_parts.append(str(session_summary))
            memory_text_parts.append("")

        long_term = memory_context.get("long_term_summary")
        if long_term:
            memory_text_parts.append("=== 长期记忆摘要 ===")
            memory_text_parts.append(f"用户目标：{long_term['user_goal']}")
            if long_term["confirmed_conditions"]:
                memory_text_parts.append(f"已确认条件：{', '.join(long_term['confirmed_conditions'])}")
            if long_term["user_preferences"]:
                memory_text_parts.append(f"用户偏好：{long_term['user_preferences']}")
            if long_term["completed_steps"]:
                memory_text_parts.append(f"已完成步骤：{', '.join(long_term['completed_steps'])}")
            if long_term["pending_items"]:
                memory_text_parts.append(f"待办事项：{', '.join(long_term['pending_items'])}")
            if long_term["key_tool_conclusions"]:
                memory_text_parts.append(f"关键工具结论：{', '.join(long_term['key_tool_conclusions'])}")
            if long_term["important_context"]:
                memory_text_parts.append(f"重要上下文：{long_term['important_context']}")
            memory_text_parts.append("")

        # 2. 中期压缩记忆
        mid_compressed = memory_context.get("mid_compressed_memory", [])
        if mid_compressed:
            memory_text_parts.append("=== 中期压缩记忆（第 6-10 条）===")
            for msg in mid_compressed:
                memory_text_parts.append(f"{msg['role']}: {msg['content']}")
            memory_text_parts.append("")

        # 3. 最近完整记忆（最高优先级）
        recent_full = memory_context.get("recent_full_memory", [])
        if recent_full:
            memory_text_parts.append("=== 最近完整记忆（最近 1-5 条，最高优先级）===")
            for msg in recent_full:
                memory_text_parts.append(f"{msg['role']}: {msg['content']}")
            memory_text_parts.append("")

        # 4. 最近工具调用结果
        tool_results = memory_context.get("latest_tool_results", [])
        if tool_results:
            memory_text_parts.append("=== 最近工具调用结果 ===")
            for tr in tool_results:
                status = "成功" if tr["success"] else "失败"
                memory_text_parts.append(
                    f"- {tr['tool_name']}: {tr['action']} ({status}) - {tr['result_summary']}"
                )
            memory_text_parts.append("")

        memory_blob = "\n".join(memory_text_parts)

        return (
            "你是一个旅行生活服务对话 Agent。\n"
            "你的职责是：理解当前用户问题，结合 Memory Agent 提供的分层记忆上下文，生成最终回复。\n\n"
            "重要规则：\n"
            "1. 当前轮用户输入最高优先级，历史记忆只能辅助理解，不能覆盖当前意图\n"
            "2. 一旦当前轮输入与历史摘要冲突，以当前轮输入为准\n"
            "3. 记忆优先级：当前输入 > 最近完整记忆 > 中期压缩记忆 > 长期摘要\n"
            "4. 不要暴露内部路由、推理过程或工具调用细节\n"
            "5. 输出格式必须统一为结构化纯文本，严格禁止使用任何 Markdown 符号（*, **, #, ##, ###, -, |, >, ```）\n"
            "6. 必须使用语义化表情符号作为标签（如 🗺️ 行程总览、🚄 推荐车次、📍 第X天、🕒 时间、🍜 午餐、🌙 晚间、🏨 住宿、⚠️ 提醒、💰 预算、🚇 交通、✅ 推荐、📷 图片）\n"
            "7. 所有回答都必须至少包含 1 个语义表情符号和 1 个颜表情，例如 (๑•̀ㅂ•́)و✧、(￣▽￣)、(｡•̀ᴗ-)✧；包括短回答、澄清问题、工具结果和兜底回复\n"
            "8. 颜表情每次回答最多 1-2 个，优先放在开头、过渡句或结尾；除非用户当前明确禁止，否则不能省略\n"
            "9. 如果内容里涉及图片，输出格式为：图片：![图片说明](图片URL)（使用标准 Markdown 图片语法）\n"
            "10. 如果信息不足，先给出简短直接回答，再用一句自然的反问引导用户补充关键信息\n"
            "11. 如果用户只是寒暄或无关当前历史，请按当前问题独立回答，不要复述旧计划\n\n"
            "=== Travel Planning 行程规划硬性规则 ===\n"
            "当用户请求完整行程规划（多日游、旅游攻略、行程安排等）时，必须严格按以下结构输出：\n\n"
            "1. 必须包含的顶层区块（按顺序）：\n"
            "   🗺️ 行程总览\n"
            "   🚄 推荐车次（如果涉及火车票）\n"
            "   📍 第1天 / 📍 第2天 / 📍 第3天（按实际天数）\n"
            "   ⚠️ 出行提醒\n\n"
            "2. 行程总览区块必须包含：\n"
            "   目的地：...\n"
            "   天数：...\n"
            "   主题：...\n"
            "   预算：...（如果用户提供）\n"
            "   适合人群：...\n"
            "   亮点：...\n\n"
            "3. 每一天的区块结构（保持块状，不要打散成平铺字段）：\n"
            "   📍 第X天\n"
            "   🏨 入住酒店/住宿：具体酒店名称，作为当天起点；不要写泛泛的“景区附近酒店”\n"
            "   🕒 上午：从XX酒店出发，前往...\n"
            "   🚇 上午景点间交通：从 A 到 B，写清推荐交通方式、预计耗时、换乘或步行提示\n"
            "   🍜 午餐：具体餐厅名称，或具体小吃街/美食街名称；不要写“附近餐厅”“附近小吃街”\n"
            "   🚇 午餐后交通：从午餐点或上午最后一个景点到下午景点，写清推荐交通方式和预计耗时\n"
            "   🕒 下午：...\n"
            "   🚇 下午景点间交通：从 C 到 D，写清推荐交通方式、预计耗时、换乘或步行提示\n"
            "   🌙 晚间建议：...\n"
            "   🚇 晚间返回交通：从晚间活动点返回当天酒店，写清具体酒店名、交通方式和预计耗时，形成闭环\n"
            "   🏨 住宿：具体酒店名称，作为下一天起点；不要写“推荐...”\n"
            "   ⚠️ 小贴士：...\n"
            "   图片：![景点名称](图片URL)（如果有）\n\n"
            "4. 景点之间交通必须具体：\n"
            "   - 每天只要安排了 2 个及以上景点，必须写出景点之间的交通衔接\n"
            "   - 优先给出地铁、公交、步行、打车、自驾中的明确方式，不要只写“前往下一站”\n"
            "   - 每段交通尽量包含起点、终点、预计耗时、换乘/步行提示\n"
            "   - 如果没有实时路线数据，可以给出保守估算并说明“约”耗时\n\n"
            "5. 酒店、餐饮和路线闭环硬性规则：\n"
            "   - 酒店必须是具体可搜索的酒店名，不能是“市中心酒店”“快捷酒店”“景区附近住宿”等泛称\n"
            "   - 餐厅必须是具体餐厅名；小吃街/美食街必须是具体地点名，不能只写“附近小吃街”\n"
            "   - 如果工具返回 POI name，必须逐字复制完整名称，例如“如家酒店(北京王府井店)”不能改成“如家酒店”\n"
            "   - 完整行程里不要写“推荐某酒店/建议某餐厅”，要直接安排：🏨 住宿：XX酒店；🍜 午餐：XX餐厅\n"
            "   - 每一天路线硬性从酒店开始，并且一定返回同一家当天酒店，形成当天闭环\n"
            "   - 全程最后一天必须回到第1天起点酒店，形成总闭环；除非用户明确要求异地结束\n"
            "   - 安排行程顺序时必须优先路程最优：少绕路、少折返、按地理顺路顺序串联景点/餐厅/晚间活动\n"
            "   - 禁止把距离很远的点硬塞在同一天导致绕圈；必要时删减或替换为顺路点\n\n"
            "6. 推荐车次区块（如果有）：\n"
            "   🚄 推荐车次\n"
            "   车次概览：...\n"
            "   推荐车次：...\n\n"
            "   车次1\n"
            "   车次：...\n"
            "   出发：...\n"
            "   到达：...\n"
            "   历时：...\n"
            "   票价：...\n"
            "   状态：...\n"
            "   推荐理由：...\n\n"
            "   车次2\n"
            "   车次：...\n"
            "   出发：...\n"
            "   到达：...\n"
            "   历时：...\n"
            "   票价：...\n"
            "   状态：...\n"
            "   推荐理由：...\n\n"
            "7. 出行提醒区块：\n"
            "   ⚠️ 出行提醒\n"
            "   💰 预算提醒：...\n"
            "   ⚠️ 预约提醒：...\n"
            "   🚇 交通提醒：...\n"
            "   ✅ 推荐建议：...\n\n"
            "8. 禁止行为：\n"
            "   - 禁止将字段打散成平铺输出（如只输出地址、推荐原因、上午、下午等零散字段）\n"
            "   - 禁止省略📍第X天的明确分段标记\n"
            "   - 禁止省略🗺️行程总览区块\n"
            "   - 禁止在多景点日省略景点之间的交通方式和预计耗时\n"
            "   - 禁止输出没有具体名称的酒店、餐厅、小吃街、美食街\n"
            "   - 禁止生成不回酒店的开放路线，除非用户明确要求单程路线\n"
            "   - 禁止将车次信息混入正文，必须独立成🚄推荐车次区块\n"
            "   - 禁止使用 Markdown 符号（*, **, #, ##, -, |, >）\n"
            "   - 必须保持块状结构，读起来像完整的 app 行程方案，不是信息碎片\n\n"
            "=== Ticket Service 票务查询硬性规则 ===\n"
            "当用户单独查询火车票信息（不是完整行程规划）时：\n\n"
            "1. 输出结构：\n"
            "   🚄 车票查询结果\n"
            "   出发地：...\n"
            "   目的地：...\n"
            "   日期：...\n"
            "   查询结果：共找到 X 趟列车\n\n"
            "   车次1\n"
            "   车次：...\n"
            "   出发：...\n"
            "   到达：...\n"
            "   历时：...\n"
            "   票价：...\n"
            "   状态：...\n"
            "   推荐理由：...\n\n"
            "   车次2\n"
            "   车次：...\n"
            "   出发：...\n"
            "   到达：...\n"
            "   历时：...\n"
            "   票价：...\n"
            "   状态：...\n"
            "   推荐理由：...\n\n"
            "   ✅ 推荐建议\n"
            "   如果赶时间：...\n"
            "   如果省钱：...\n"
            "   如果舒适：...\n\n"
            "   ⚠️ 购票提醒\n"
            "   - ...\n"
            "   - ...\n\n"
            "2. 数量要求：\n"
            "   - 必须输出 3-8 趟列车\n"
            "   - 如果少于3趟，明确说明：'当前仅找到 X 趟列车'\n"
            "   - 按出发时间排序\n\n"
            "3. 禁止行为：\n"
            "   - 禁止使用 Markdown 表格格式\n"
            "   - 必须使用文字卡片格式（车次1、车次2...）\n"
            "   - 保持结构清晰，易于阅读\n\n"
            "=== 酒店/餐厅推荐硬性规则 ===\n"
            "当用户单独请求酒店或餐厅推荐（不是完整行程规划）时：\n\n"
            "1. 数量要求（强制）：\n"
            "   - 推荐酒店时，必须输出 3-5 个具体酒店\n"
            "   - 推荐餐厅时，必须输出 3-5 个具体餐厅\n"
            "   - 同时推荐酒店和餐厅时，酒店 3-5 个 + 餐厅 3-5 个\n"
            "   - 如果数据不足 3 个，必须明确说明：'当前仅找到 X 个可靠候选'\n"
            "   - 禁止只输出 1-2 个就停止\n\n"
            "2. 名称识别规则（关键）：\n"
            "   - 酒店/餐厅的真实名称必须来自工具返回的 POI 数据中的 'name' 字段\n"
            "   - 【强制】必须使用工具返回的完整准确名称，一字不差，不允许任何修改、简化或泛化\n"
            "   - 不要把类型名称（如'经济型酒店''快捷酒店''中餐厅'）当作酒店名称\n"
            "   - 不要把平台名称或分类标签当作酒店名称\n"
            "   - 【关键】每个酒店/餐厅的名称必须与工具返回的 POI name 完全一致，包括所有字符、空格、标点\n"
            "   - 如果工具返回的名称是'如家酒店(北京王府井店)'，输出时必须完全一致，不能改为'如家酒店'或'如家王府井店'\n\n"
            "3. 图片匹配规则（关键）：\n"
            "   - 每个酒店/餐厅的图片必须来自工具返回的该 POI 的 photos 字段\n"
            "   - 【强制】酒店名称和图片必须来自同一个 POI 数据，通过 name 字段精确匹配\n"
            "   - 禁止将 POI A 的图片用于 POI B\n"
            "   - 如果某个 POI 没有图片数据，不要为其添加图片\n"
            "   - 【关键】输出酒店/餐厅名称时，必须与工具返回的 name 字段完全一致（包括所有字符），这样图片才能正确匹配\n"
            "   - 图片 URL 必须与名称严格对应，系统会根据完全一致的名称进行图片绑定\n\n"
            "4. 输出格式（强制）：\n"
            "   🏨 住宿推荐\n\n"
            "   酒店1\n"
            "   酒店名称：[工具返回的完整准确名称]\n"
            "   地址：[工具返回的地址]\n"
            "   适合：[适合人群]\n"
            "   推荐原因：[具体原因]\n"
            "   图片：![酒店名称](该酒店的图片URL)\n\n"
            "   酒店2\n"
            "   酒店名称：[工具返回的完整准确名称]\n"
            "   地址：[工具返回的地址]\n"
            "   适合：[适合人群]\n"
            "   推荐原因：[具体原因]\n"
            "   图片：![酒店名称](该酒店的图片URL)\n\n"
            "   🍜 餐饮推荐\n\n"
            "   餐厅1\n"
            "   餐厅名称：[工具返回的完整准确名称]\n"
            "   地址：[工具返回的地址]\n"
            "   类型：[餐厅类型]\n"
            "   推荐原因：[具体原因]\n"
            "   图片：![餐厅名称](该餐厅的图片URL)\n\n"
            "5. 禁止行为：\n"
            "   - 禁止将宽泛区域（如'市中心附近''景区周边'）当作推荐条目\n"
            "   - 禁止在卡片底部重复显示酒店名称\n"
            "   - 禁止把图片集中放在最后，必须放在对应条目内\n"
            "   - 禁止使用 Markdown 符号（*, **, #, ##, -, |, >）\n"
            "   - 禁止混淆不同 POI 的名称和图片\n"
            "   - 禁止修改工具返回的 POI 名称\n\n"
            f"skill 名称：{self.skill.name}\n"
            f"skill 描述：{self.skill.description}\n\n"
            f"skill 原文：\n{self.skill_text}\n\n"
            f"selected module：{module}\n"
            f"module reference：\n{reference_blob}\n\n"
            "=== 分层记忆上下文 ===\n"
            f"{memory_blob}\n"
            "请基于当前用户问题和上述分层记忆，输出自然、简洁、适合手机阅读的中文回答。"
        )

    def _enforce_output_count(self, content: str, poi_data: list[dict[str, Any]]) -> str:
        """强制确保输出3-5个POI"""
        if not poi_data or len(poi_data) < 3:
            return content

        lines = content.split("\n")

        # 统计已输出的酒店和餐厅数量
        hotel_count = 0
        restaurant_count = 0

        for line in lines:
            if re.match(r"^酒店\s*\d+", line.strip()):
                hotel_count += 1
            elif re.match(r"^餐厅\s*\d+", line.strip()):
                restaurant_count += 1

        # 检查是否需要补充
        needs_hotels = "酒店" in content and hotel_count < 3
        needs_restaurants = "餐厅" in content and restaurant_count < 3

        if not needs_hotels and not needs_restaurants:
            return content

        # 构建补充内容
        supplement_lines = []

        if needs_hotels:
            # 找到可用的酒店POI
            available_hotels = [poi for poi in poi_data if "酒店" in poi.get("type", "") or "hotel" in poi.get("type", "").lower()]
            if not available_hotels:
                available_hotels = poi_data[:5]  # 使用前5个POI

            # 补充到3个
            for i in range(hotel_count, min(3, len(available_hotels))):
                poi = available_hotels[i]
                supplement_lines.append(f"\n酒店{i+1}")
                supplement_lines.append(f"酒店名称：{poi['name']}")
                if poi.get('address'):
                    supplement_lines.append(f"地址：{poi['address']}")
                supplement_lines.append(f"推荐原因：位置便利，设施完善")
                if poi.get('photos'):
                    supplement_lines.append(f"图片：![{poi['name']}]({poi['photos'][0]})")

        if needs_restaurants:
            # 找到可用的餐厅POI
            available_restaurants = [poi for poi in poi_data if "餐厅" in poi.get("type", "") or "restaurant" in poi.get("type", "").lower()]
            if not available_restaurants:
                available_restaurants = poi_data[:5]

            # 补充到3个
            for i in range(restaurant_count, min(3, len(available_restaurants))):
                poi = available_restaurants[i]
                supplement_lines.append(f"\n餐厅{i+1}")
                supplement_lines.append(f"餐厅名称：{poi['name']}")
                if poi.get('address'):
                    supplement_lines.append(f"地址：{poi['address']}")
                supplement_lines.append(f"推荐原因：口碑良好，值得一试")
                if poi.get('photos'):
                    supplement_lines.append(f"图片：![{poi['name']}]({poi['photos'][0]})")

        if supplement_lines:
            print(f"[DEBUG] 补充输出: 酒店 {hotel_count}→3, 餐厅 {restaurant_count}→3")
            return content + "\n" + "\n".join(supplement_lines)

        return content

    def _post_process_output(self, content: str, poi_data: list[dict[str, Any]]) -> str:
        """后处理输出，确保图片和名称严格对应"""
        if not poi_data:
            return content

        # 构建名称到图片的映射
        name_to_photo: dict[str, str] = {}
        for poi in poi_data:
            name = poi.get("name", "").strip()
            photos = poi.get("photos", [])
            if name and photos:
                name_to_photo[name] = photos[0]

        if not name_to_photo:
            return content

        lines = content.split("\n")
        result_lines = []
        current_poi_name = None

        for line in lines:
            # 检测是否是名称行
            for label in ["酒店名称：", "餐厅名称：", "名称："]:
                if label in line:
                    # 提取名称
                    name_part = line.split(label, 1)[1].strip()
                    # 检查是否在映射中
                    if name_part in name_to_photo:
                        current_poi_name = name_part
                    break

            # 检测是否是图片行
            if line.strip().startswith("图片：") and current_poi_name:
                # 检查图片URL是否正确
                if current_poi_name in name_to_photo:
                    correct_photo = name_to_photo[current_poi_name]
                    # 重新构建图片行，确保名称和URL匹配
                    line = f"图片：![{current_poi_name}]({correct_photo})"
                    print(f"[DEBUG] 修正图片行: {current_poi_name} -> {correct_photo}")

            result_lines.append(line)

            # 如果遇到新的POI项，重置当前名称
            if re.match(r"^(酒店|餐厅)\s*\d+", line.strip()):
                current_poi_name = None

        return "\n".join(result_lines)

    async def generate_response(
        self,
        current_input: str,
        memory_context: dict[str, Any],
        user_id: int | None = None,
        top_k: int | None = None,
    ) -> tuple[str, list[dict[str, Any]]]:
        """生成回复 - 基于当前输入和记忆上下文，支持工具调用

        Returns:
            (final_content, poi_data) - 回复文本和POI数据列表
        """
        agent = await self._get_agent(user_id=user_id, top_k=top_k)
        system_prompt = self._build_system_prompt(memory_context, current_input)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": current_input},
        ]

        # 第一次调用：让 LLM 调用工具获取数据
        response = await agent.ainvoke({"messages": messages})
        all_messages = response.get("messages", []) if isinstance(response, dict) else []

        # 检查是否有工具调用
        has_tool_calls = any(getattr(msg, "type", "") == "tool" for msg in all_messages)

        poi_data = []
        if has_tool_calls:
            # 提取 POI 数据
            poi_data = self._extract_poi_data_from_tools(all_messages)

            if poi_data:
                # 构建包含 POI 数据的新提示
                poi_instruction = self._build_poi_instruction(poi_data)

                # 将所有消息添加到上下文中
                for msg in all_messages:
                    messages.append(msg)

                # 添加新的指令，要求基于 POI 数据生成输出
                messages.append({
                    "role": "system",
                    "content": (
                        f"{poi_instruction}\n\n"
                        "【最终提醒】\n"
                        "1. 必须输出 3-5 个推荐（强制要求）\n"
                        "2. 每个推荐的名称必须与 POI 数据中的 name 字段完全一致（逐字复制）\n"
                        "3. 每个推荐的图片必须使用对应 POI 的 photo 字段\n"
                        "4. 通过 poi_id 确保名称和图片来自同一个 POI\n"
                        "5. 图片格式：图片：![POI名称](photo_url)\n"
                        "6. 现在立即生成输出，严格遵守以上规则"
                    )
                })

                # 第二次调用：基于 POI 数据生成最终输出
                response = await agent.ainvoke({"messages": messages})
                all_messages = response.get("messages", []) if isinstance(response, dict) else []

        # 提取最终文本
        if all_messages:
            content = getattr(all_messages[-1], "content", all_messages[-1])
        else:
            content = getattr(response, "content", response)

        final_content = str(content).strip()

        # 后处理：确保图片和名称严格对应
        if poi_data:
            deterministic_content = self._build_deterministic_poi_response(current_input, poi_data)
            if deterministic_content:
                final_content = deterministic_content
            else:
                final_content = self._post_process_output(final_content, poi_data)
                # 强制确保输出3-5个POI
                final_content = self._enforce_output_count(final_content, poi_data)

        if self._needs_itinerary_transport_repair(current_input, final_content):
            final_content = await self._repair_itinerary_transport(agent, messages, current_input, final_content)
            final_content = self._ensure_itinerary_transport_fallback(current_input, final_content)

        final_content = self._ensure_required_expressions(final_content)

        # 构建前端可用的 POI 列表（含坐标）
        frontend_pois = [
            {k: v for k, v in p.items() if k in ("poi_id", "name", "address", "lng", "lat", "location", "photos", "type", "rating")}
            for p in poi_data
        ]

        return final_content, frontend_pois
