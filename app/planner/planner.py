"""
Sistema de Planificación de Itinerarios Turísticos Optimizado
"""

import random
import numpy as np
import math
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)

# Enums simplificados
class WeatherCondition(Enum):
    SUNNY = "soleado"
    CLOUDY = "nublado" 
    RAINY = "lluvioso"
    STORMY = "tormentoso"

class ActivityType(Enum):
    TOUR = "tour"
    CULTURAL = "cultural"
    MUSEUM = "museo"
    EXCURSION = "excursion"
    RESTAURANT = "restaurante"
    TRANSPORT = "transporte"
    NATURE = "naturaleza"
    ENTERTAINMENT = "entretenimiento"
    SHOPPING = "compras"
    ACCOMMODATION = "alojamiento"

@dataclass
class Location:
    """Ubicación geográfica con cálculo de distancia"""
    name: str
    latitude: float
    longitude: float
    
    def distance_to(self, other: 'Location') -> float:
        """Distancia en km usando Haversine"""
        R = 6371
        lat1, lon1 = math.radians(self.latitude), math.radians(self.longitude)
        lat2, lon2 = math.radians(other.latitude), math.radians(other.longitude)
        
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

@dataclass
class TourismActivity:
    """Actividad turística simplificada"""
    id: str
    name: str
    activity_type: ActivityType
    location: Location
    duration_minutes: int
    cost: float
    rating: float  # 1-5
    description: str
    
    # Configuración simplificada
    start_hour: int = 9
    end_hour: int = 17
    indoor: bool = True
    interest_categories: List[str] = field(default_factory=list)
    
    def is_available_at(self, dt: datetime) -> bool:
        """Verifica disponibilidad en horario"""
        return self.start_hour <= dt.hour < self.end_hour
    
    def get_weather_penalty(self, weather: WeatherCondition) -> float:
        """Penalización por clima (0-1)"""
        if self.indoor:
            return 0.1
        return 0.8 if weather in [WeatherCondition.RAINY, WeatherCondition.STORMY] else 0.1

@dataclass
class UserPreferences:
    """Preferencias del usuario simplificadas"""
    start_date: datetime
    end_date: datetime
    max_budget: float = 0.0  # 0 significa sin límite de presupuesto
    daily_start_hour: int = 9
    daily_end_hour: int = 18
    max_daily_duration: int = 480  # minutos
    max_walking_distance: float = 5.0  # km
    interest_categories: List[str] = field(default_factory=list)
    
    # Pesos de importancia
    weights: Dict[str, float] = field(default_factory=lambda: {
        'cost': 0.25, 'time': 0.2, 'rating': 0.25, 'weather': 0.15, 'interest': 0.15
    })

@dataclass
class ItineraryItem:
    """Item en itinerario"""
    activity: TourismActivity
    start_time: datetime
    transport_time: int = 15  # minutos
    transport_cost: float = 5.0

@dataclass 
class DayPlan:
    """Plan diario"""
    date: datetime
    items: List[ItineraryItem] = field(default_factory=list)
    weather: WeatherCondition = WeatherCondition.SUNNY
    
    def get_duration(self) -> int:
        return sum(item.activity.duration_minutes + item.transport_time for item in self.items)
    
    def get_cost(self) -> float:
        return sum(item.activity.cost + item.transport_cost for item in self.items)
    
    def get_walking_distance(self) -> float:
        if len(self.items) <= 1:
            return 0.0
        
        # Filter out items without location
        items_with_location = [item for item in self.items if item.activity.location is not None]
        if len(items_with_location) <= 1:
            return 0.0
        
        # Calculate distances only between consecutive activities with locations
        total_distance = 0.0
        for i in range(len(items_with_location)-1):
            total_distance += items_with_location[i].activity.location.distance_to(
                items_with_location[i+1].activity.location
            )
        return total_distance

class Itinerary:
    """Itinerario completo optimizado"""
    
    def __init__(self, days: List[DayPlan] = None):
        self.days = days or []
        self.fitness_score: float = 0.0
    
    def get_total_cost(self) -> float:
        return sum(day.get_cost() for day in self.days)
    
    def get_average_rating(self) -> float:
        items = [item for day in self.days for item in day.items]
        return sum(item.activity.rating for item in items) / len(items) if items else 0.0
    
    def clone(self) -> 'Itinerary':
        """Copia eficiente"""
        new_days = []
        for day in self.days:
            new_items = [
                ItineraryItem(item.activity, item.start_time, item.transport_time, item.transport_cost)
                for item in day.items
            ]
            new_days.append(DayPlan(day.date, new_items, day.weather))
        return Itinerary(new_days)

class ItineraryEvaluator:
    """Evaluador optimizado con cálculos vectorizados"""
    
    def __init__(self, preferences: UserPreferences):
        self.preferences = preferences
        self.weights = preferences.weights
    
    def evaluate(self, itinerary: Itinerary) -> float:
        """Evaluación rápida multi-criterio"""
        if not itinerary.days:
            return 0.0
        
        # Calcular métricas básicas
        total_cost = itinerary.get_total_cost()
        avg_rating = itinerary.get_average_rating()
        
        # Scores normalizados (0-1)
        cost_score = max(0, 1 - total_cost / self.preferences.max_budget)
        rating_score = avg_rating / 5.0
        time_score = self._calculate_time_efficiency(itinerary)
        weather_score = self._calculate_weather_score(itinerary)
        interest_score = self._calculate_interest_score(itinerary)
        
        # Penalizaciones por violaciones
        penalty = self._calculate_violations(itinerary)
        
        # Score final ponderado
        final_score = (
            self.weights['cost'] * cost_score +
            self.weights['rating'] * rating_score +
            self.weights['time'] * time_score +
            self.weights['weather'] * weather_score +
            self.weights['interest'] * interest_score -
            penalty
        )
        
        return max(0, final_score)
    
    def _calculate_time_efficiency(self, itinerary: Itinerary) -> float:
        """Eficiencia de tiempo: actividades vs transporte"""
        activity_time = sum(sum(item.activity.duration_minutes for item in day.items) 
                           for day in itinerary.days)
        transport_time = sum(sum(item.transport_time for item in day.items) 
                           for day in itinerary.days)
        
        total_time = activity_time + transport_time
        return activity_time / total_time if total_time > 0 else 0.0
    
    def _calculate_weather_score(self, itinerary: Itinerary) -> float:
        """Score de compatibilidad climática"""
        penalties = []
        for day in itinerary.days:
            for item in day.items:
                penalties.append(item.activity.get_weather_penalty(day.weather))
        
        return 1.0 - np.mean(penalties) if penalties else 1.0
    
    def _calculate_interest_score(self, itinerary: Itinerary) -> float:
        """Score de coincidencia de intereses"""
        if not self.preferences.interest_categories:
            return 1.0
        
        user_interests = set(self.preferences.interest_categories)
        matches = []
        
        for day in itinerary.days:
            for item in day.items:
                activity_interests = set(item.activity.interest_categories)
                match_ratio = len(user_interests & activity_interests) / len(user_interests)
                matches.append(match_ratio)
        
        return np.mean(matches) if matches else 0.0
    
    def _calculate_violations(self, itinerary: Itinerary) -> float:
        """Penalizaciones por violaciones de restricciones"""
        penalty = 0.0
        
        for day in itinerary.days:
            # Violación de duración diaria
            if day.get_duration() > self.preferences.max_daily_duration:
                penalty += 0.5
            
            # Violación de distancia
            if day.get_walking_distance() > self.preferences.max_walking_distance:
                penalty += 0.3
            
            # Violación de horarios
            for item in day.items:
                if not item.activity.is_available_at(item.start_time):
                    penalty += 0.2
        
        # Violación de presupuesto solo si hay límite establecido
        if self.preferences.max_budget > 0 and itinerary.get_total_cost() > self.preferences.max_budget:
            penalty += 1.0
        
        return penalty

class GeneticAlgorithmPlanner:
    """Algoritmo Genético optimizado para planificación turística"""
    
    def __init__(self, activities: List[TourismActivity], preferences: UserPreferences,
                 population_size: int = 30, mutation_rate: float = 0.15):
        self.activities = activities
        self.preferences = preferences
        self.evaluator = ItineraryEvaluator(preferences)
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.population: List[Itinerary] = []
        self.best_solution: Optional[Itinerary] = None
        self.best_score: float = 0.0
        # Tracking de actividades usadas
        self.used_activities: Set[str] = set()
        
    def get_available_activities(self, budget: float) -> List[TourismActivity]:
        """Obtiene actividades disponibles que no han sido usadas"""
        if budget <= 0:  # Sin límite de presupuesto
            return [a for a in self.activities if a.id not in self.used_activities]
        return [a for a in self.activities 
                if (a.cost is None or a.cost <= budget)
                and a.id not in self.used_activities]
    
    def optimize(self, max_iterations: int = 500) -> Itinerary:
        """Optimización principal"""
        logger.info(f"Iniciando optimización GA: {self.population_size} individuos, {max_iterations} iteraciones")
        
        # Reiniciar tracking de actividades
        self.used_activities.clear()
        
        # Inicializar población
        self._initialize_population()
        
        for generation in range(max_iterations):
            # Evaluar y actualizar mejor solución
            fitness_scores = self._evaluate_population()
            self._update_best_solution(fitness_scores)
            
            # Log progreso cada 50 generaciones
            if generation % 50 == 0:
                avg_fitness = np.mean(fitness_scores)
                logger.info(f"Gen {generation}: Avg={avg_fitness:.3f}, Best={self.best_score:.3f}")
            
            # Crear nueva generación
            self.population = self._create_next_generation(fitness_scores)
            
            # Convergencia temprana
            if generation > 100 and np.std(fitness_scores) < 0.01:
                logger.info(f"Convergencia en generación {generation}")
                break
        
        return self.best_solution
    
    def _initialize_population(self):
        """Inicialización eficiente de población"""
        self.population = [self._generate_random_itinerary() for _ in range(self.population_size)]
    
    def _generate_random_itinerary(self) -> Itinerary:
        """Generación aleatoria optimizada"""
        days = []
        current_date = self.preferences.start_date
        daily_budget = self.preferences.max_budget / max(1, (self.preferences.end_date - self.preferences.start_date).days + 1)
        
        while current_date <= self.preferences.end_date:
            day_plan = self._generate_random_day(current_date, daily_budget)
            days.append(day_plan)
            current_date += timedelta(days=1)
        
        return Itinerary(days)
    
    def _generate_random_day(self, date: datetime, budget: float) -> DayPlan:
        """Generación de día aleatorio con restricciones"""
        available_activities = self.get_available_activities(budget)
        if not available_activities:
            return DayPlan(date=date, weather=random.choice(list(WeatherCondition)))
        
        selected_items = []
        current_time = date.replace(hour=self.preferences.daily_start_hour)
        current_cost = 0.0
        
        # Selección greedy-aleatoria
        while (current_time.hour < self.preferences.daily_end_hour - 1 and available_activities):
            # Seleccionar con sesgo hacia actividades mejor valoradas
            weights = [a.rating for a in available_activities]
            activity = random.choices(available_activities, weights=weights)[0]
            available_activities.remove(activity)
            self.used_activities.add(activity.id)
            
            # Solo verificar presupuesto si hay límite
            if budget <= 0 or current_cost + activity.cost <= budget:
                item = ItineraryItem(
                    activity=activity,
                    start_time=current_time,
                    transport_time=random.randint(10, 20),
                    transport_cost=random.uniform(3, 8)
                )
                selected_items.append(item)
                current_cost += activity.cost + item.transport_cost
                current_time += timedelta(minutes=activity.duration_minutes + item.transport_time)
        
        return DayPlan(
            date=date, 
            items=selected_items,
            weather=random.choice(list(WeatherCondition))
        )
        
    def _evaluate_population(self) -> List[float]:
        """Evaluación vectorizada de población"""
        fitness_scores = []
        for individual in self.population:
            score = self.evaluator.evaluate(individual)
            individual.fitness_score = score
            fitness_scores.append(score)
        return fitness_scores
    
    def _update_best_solution(self, fitness_scores: List[float]):
        """Actualización eficiente de mejor solución"""
        max_idx = np.argmax(fitness_scores)
        max_score = fitness_scores[max_idx]
        
        if max_score > self.best_score:
            self.best_score = max_score
            self.best_solution = self.population[max_idx].clone()
    
    def _create_next_generation(self, fitness_scores: List[float]) -> List[Itinerary]:
        """Generación optimizada con elitismo"""
        new_population = []
        
        # Elitismo: top 10%
        elite_size = max(2, self.population_size // 10)
        elite_indices = np.argsort(fitness_scores)[-elite_size:]
        new_population.extend(self.population[i].clone() for i in elite_indices)
        
        # Generar resto por selección y operadores genéticos
        while len(new_population) < self.population_size:
            parent1 = self._tournament_selection(fitness_scores)
            parent2 = self._tournament_selection(fitness_scores)
            
            # Cruce simple
            child = self._crossover(parent1, parent2)
            
            # Mutación
            if random.random() < self.mutation_rate:
                child = self._mutate(child)
            
            new_population.append(child)
        
        return new_population[:self.population_size]
    
    def _tournament_selection(self, fitness_scores: List[float], k: int = 3) -> Itinerary:
        """Selección por torneo optimizada"""
        tournament_indices = random.sample(range(len(self.population)), min(k, len(self.population)))
        best_idx = max(tournament_indices, key=lambda i: fitness_scores[i])
        return self.population[best_idx]
    
    def _crossover(self, parent1: Itinerary, parent2: Itinerary) -> Itinerary:
        """Cruce uniforme por días manteniendo unicidad de actividades"""
        if len(parent1.days) != len(parent2.days):
            return random.choice([parent1, parent2]).clone()
        
        # Limpiar tracking para el nuevo hijo
        self.used_activities.clear()
        child_days = []
        
        for i in range(len(parent1.days)):
            # Selección aleatoria de día padre
            selected_day = random.choice([parent1.days[i], parent2.days[i]])
            
            # Verificar actividades no usadas
            valid_items = []
            for item in selected_day.items:
                if item.activity.id not in self.used_activities:
                    valid_items.append(item)
                    self.used_activities.add(item.activity.id)
            
            # Crear nuevo día solo con actividades válidas
            child_days.append(DayPlan(
                date=selected_day.date,
                items=valid_items,
                weather=selected_day.weather
            ))
        
        return Itinerary(child_days)
    
    def _mutate(self, individual: Itinerary) -> Itinerary:
        """Mutación eficiente"""
        mutated = individual.clone()
        
        if not mutated.days:
            return mutated
        
        # Seleccionar tipo de mutación
        mutation_ops = [self._mutate_swap, self._mutate_replace, self._mutate_shuffle]
        random.choice(mutation_ops)(mutated)
        
        return mutated
    
    def _mutate_swap(self, itinerary: Itinerary):
        """Intercambio de actividades entre días"""
        if len(itinerary.days) < 2:
            return
        
        day1, day2 = random.sample(itinerary.days, 2)
        if day1.items and day2.items:
            item1, item2 = random.choice(day1.items), random.choice(day2.items)
            day1.items.remove(item1)
            day2.items.remove(item2)
            day1.items.append(item2)
            day2.items.append(item1)
    
    def _mutate_replace(self, itinerary: Itinerary):
        """Reemplazo de actividad manteniendo unicidad"""
        day = random.choice(itinerary.days)
        if not day.items:
            return
        
        old_item = random.choice(day.items)
        # Liberar actividad actual
        self.used_activities.remove(old_item.activity.id)
        
        # Buscar nueva actividad no usada
        available_activities = self.get_available_activities(old_item.activity.cost * 1.2)
        if available_activities:
            new_activity = random.choice(available_activities)
            self.used_activities.add(new_activity.id)
            
            new_item = ItineraryItem(
                activity=new_activity,
                start_time=old_item.start_time,
                transport_time=old_item.transport_time,
                transport_cost=old_item.transport_cost
            )
            
            day.items.remove(old_item)
            day.items.append(new_item)
        else:
            # Si no hay actividades disponibles, restaurar la anterior
            self.used_activities.add(old_item.activity.id)
    
    def _mutate_shuffle(self, itinerary: Itinerary):
        """Reordenamiento de actividades en un día"""
        day = random.choice(itinerary.days)
        if len(day.items) > 1:
            random.shuffle(day.items)

# Función helper para uso simplificado
def create_tourism_planner(activities: List[TourismActivity], 
                          preferences: UserPreferences) -> GeneticAlgorithmPlanner:
    """Factory function para crear planificador optimizado"""
    return GeneticAlgorithmPlanner(activities, preferences)