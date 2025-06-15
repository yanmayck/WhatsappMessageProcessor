import googlemaps
from config import Config
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class GeolocationService:
    def __init__(self):
        if not Config.GOOGLE_MAPS_API_KEY:
            logger.warning("GOOGLE_MAPS_API_KEY não está configurada. GeolocationService não funcionará.")
            self.gmaps = None
        else:
            self.gmaps = googlemaps.Client(key=Config.GOOGLE_MAPS_API_KEY)

    def get_distance_and_duration(self, origin: str, destination: str) -> Optional[Tuple[float, str, int, str]]:
        """
        Calcula a distância (em km) e a duração (em texto e segundos) entre uma origem e um destino.
        Retorna uma tupla (distancia_km, distancia_texto, duracao_segundos, duracao_texto) ou None se falhar.
        """
        if not self.gmaps:
            logger.error("Google Maps client não inicializado. Verifique a API Key.")
            return None

        try:
            directions_result = self.gmaps.directions(
                origin,
                destination,
                mode="driving", # Pode ser "walking", "bicycling", "transit"
                language="pt-BR"
            )

            if directions_result and len(directions_result) > 0:
                leg = directions_result[0]['legs'][0]
                distance_meters = leg['distance']['value']
                distance_km = distance_meters / 1000.0
                distance_text = leg['distance']['text']
                
                duration_seconds = leg['duration']['value']
                duration_text = leg['duration']['text']
                
                logger.info(f"Distância de '{origin}' para '{destination}': {distance_text} ({distance_km:.2f} km), Duração: {duration_text} ({duration_seconds} s)")
                return distance_km, distance_text, duration_seconds, duration_text
            else:
                logger.warning(f"Não foi possível calcular a distância entre '{origin}' e '{destination}'. Resposta da API: {directions_result}")
                return None
        except googlemaps.exceptions.ApiError as e:
            logger.error(f"Erro na API do Google Maps ao calcular distância: {e}")
            return None
        except Exception as e:
            logger.error(f"Erro inesperado ao calcular distância: {e}", exc_info=True)
            return None

    def calculate_shipping_fee(self, distance_km: float, base_fee: float = 5.0, fee_per_km: float = 1.5) -> float:
        """
        Calcula a taxa de frete com base na distância.
        Exemplo simples: uma taxa base + uma taxa por km.
        """
        if distance_km < 0:
            return 0.0
        
        total_fee = base_fee + (distance_km * fee_per_km)
        logger.info(f"Taxa de frete calculada para {distance_km:.2f} km: R$ {total_fee:.2f}")
        return round(total_fee, 2)

# Exemplo de uso (pode ser removido ou comentado)
if __name__ == '__main__':
    # Certifique-se de ter GOOGLE_MAPS_API_KEY definida no seu ambiente ou config local para testar
    if Config.GOOGLE_MAPS_API_KEY:
        geo_service = GeolocationService()
        
        # Exemplo 1: Endereços como strings
        # Substitua pelos endereços de teste desejados
        origin_address = "Av. Paulista, 1578, São Paulo, SP"
        destination_address = "Rua Oscar Freire, 439, São Paulo, SP"
        
        result = geo_service.get_distance_and_duration(origin_address, destination_address)
        
        if result:
            dist_km, dist_text, dur_sec, dur_text = result
            print(f"De: {origin_address}")
            print(f"Para: {destination_address}")
            print(f"Distância: {dist_text} ({dist_km:.2f} km)")
            print(f"Duração: {dur_text}")
            
            shipping_cost = geo_service.calculate_shipping_fee(dist_km)
            print(f"Custo do Frete Estimado: R$ {shipping_cost:.2f}")
        else:
            print("Não foi possível calcular a distância.")

        # Exemplo 2: Coordenadas (lat,lng) - API do Google aceita
        # origin_coords = "-23.561399, -46.656087" # Av Paulista 1578 (aprox)
        # destination_coords = "-23.560278, -46.669880" # Oscar Freire 439 (aprox)
        # result_coords = geo_service.get_distance_and_duration(origin_coords, destination_coords)
        # if result_coords:
        #     dist_km_coords, _, _, _ = result_coords
        #     shipping_cost_coords = geo_service.calculate_shipping_fee(dist_km_coords)
        #     print(f"Custo do Frete (coords): R$ {shipping_cost_coords:.2f}")

    else:
        print("GOOGLE_MAPS_API_KEY não configurada. Não é possível testar GeolocationService.") 