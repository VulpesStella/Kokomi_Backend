from app.core import EnvConfig
from app.loggers import ExceptionLogger
from app.models import ClanModel
from app.response import JSONResponse
from app.utils import JsonUtils


class ClanRankingAPI:
    PAGE_SIZE = 50

    @staticmethod
    async def _get_ranking_base_data(is_specify: bool) -> dict:
        season_data = JsonUtils.read('clan_season')
        if is_specify:
            ranking_data = {
                'page': 0,
                'info': {
                    'region': EnvConfig.REGION,
                    'season': season_data.get('id', 0)
                },
                'rank': 0,
                'datas': []
            }
        else:
            ranking_data = {
                'page': 0,
                'info': {
                    'region': EnvConfig.REGION,
                    'season': season_data.get('id', 0)
                },
                'datas': []
            }
        return ranking_data

    @ExceptionLogger.handle_program_exception_async
    async def get_clan_ranking(page: int = 1):
        ranking_data = await ClanRankingAPI._get_ranking_base_data(False)

        if page <= 0:
            page = 1

        season_id = ranking_data['info']['season']
        ok, leaderboard = JSONResponse.extract_data(
            response=await ClanModel.fetch_clan_leaderboard_page(
                season_id,
                page,
                ClanRankingAPI.PAGE_SIZE
            )
        )
        if not ok:
            return leaderboard

        if not leaderboard:
            return JSONResponse.API_2022_NoRankingDataForClanSeason

        ranking_data['page'] = page
        ranking_data['datas'] = leaderboard
        return JSONResponse.get_success_response(ranking_data)

    @ExceptionLogger.handle_program_exception_async
    async def get_clan_specify_ranking(clan_id: int):
        ranking_data = await ClanRankingAPI._get_ranking_base_data(True)

        season_id = ranking_data['info']['season']
        ok, clan_rank_data = JSONResponse.extract_data(
            response=await ClanModel.fetch_clan_leaderboard_rank(season_id, clan_id)
        )
        if not ok:
            return clan_rank_data

        if clan_rank_data is None:
            return JSONResponse.API_2021_NoRankingDataForClan

        rank = clan_rank_data['rank']
        page = ((rank - 1) // ClanRankingAPI.PAGE_SIZE) + 1

        ok, leaderboard = JSONResponse.extract_data(
            response=await ClanModel.fetch_clan_leaderboard_page(
                season_id,
                page,
                ClanRankingAPI.PAGE_SIZE
            )
        )
        if not ok:
            return leaderboard

        if not leaderboard:
            return JSONResponse.API_2022_NoRankingDataForClanSeason

        ranking_data['rank'] = rank
        ranking_data['page'] = page
        ranking_data['datas'] = leaderboard
        return JSONResponse.get_success_response(ranking_data)
