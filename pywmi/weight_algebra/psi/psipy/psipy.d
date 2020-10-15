import std.conv;
import std.algorithm;
import std.format;
import std.parallelism;
import std.bigint;

import options, hashtable, dutil;

import pyd.pyd;

import dparse;
import dexpr;
import distrib;
import integration;



class TypeError : Exception
{
    this(string msg, string file = __FILE__, size_t line = __LINE__) {
        super(msg, file, line);
    }
}

class NotImplementedError : Exception
{
    this(string msg, string file = __FILE__, size_t line = __LINE__) {
        super(msg, file, line);
    }
}



auto S(string symbol){
   return new PsiExpr(symbol.dParse.simplify(one));
}
auto S(int number){
   return new PsiExpr(to!string(number).dParse.simplify(one));
}
auto S(float number){
   return new PsiExpr(to!string(number).dParse.simplify(one));
}
auto S(double number){
   return new PsiExpr(to!string(number).dParse.simplify(one));
}

auto toSympyString(Polynomial p){
   return p._polynomial._expression.toString(Format.sympy);
}


class EvalBoundsCache{
   static MapX!(Q!(DExpr,long),DExpr) _cache;

   DExpr retrieve_cache(DExpr bound, long degree){
      if  (q(bound,degree) in _cache){
         return _cache[q(bound,degree)];
      }
      else if (degree==2){
         auto result = (bound*bound).simplify(one);
         _cache[q(bound,degree)] = result;
         return result;
      }
      else if (degree>2){
         auto result = (retrieve_cache(bound, degree-1)*bound).simplify(one);
         _cache[q(bound,degree)] = result;
         return result;
      }
      else{
         return (bound^^degree).simplify(one);
      }
   }
}


class PsiExpr{
   dexpr.DExpr _expression;
   this(dexpr.DExpr expression){
      _expression = expression;
   }


   override string toString(){
      return _expression.toString();
   }

   auto variables(){
      PsiExpr[] variables;
      foreach(v;_expression.freeVars){
         variables ~= new PsiExpr(v);
      }
      return variables;
   }

   auto is_equal(PsiExpr other){
      return _expression == other._expression;
   }

   auto is_polynomial(){
      return isPolynomial(_expression);
   }

   auto is_zero(){
      return _expression==zero;
   }
   auto is_one(){
      return _expression==one;
   }
   auto is_iverson(){
      if (auto dummy = cast(DIvr)_expression) return 1;
      else return 0;
   }


   auto simplify(){
      return  new PsiExpr(_expression.simplify(one));
   }

   auto opBinary(string op)(PsiExpr rhs) if(op == "+"){
      return new PsiExpr(_expression + rhs._expression);
   }
   auto opBinary(string op)(PsiExpr rhs) if(op == "-"){
      return new PsiExpr(_expression - rhs._expression);
   }
   auto opBinary(string op)(PsiExpr rhs) if(op == "*"){
      return new PsiExpr(_expression * rhs._expression);
   }
   auto opBinary(string op)(PsiExpr rhs) if(op == "/"){
      return new PsiExpr(_expression / rhs._expression);
   }
   auto opBinary(string op)(PsiExpr rhs) if(op == "^^"){
      return new PsiExpr(_expression ^^ rhs._expression);
   }


   auto eq(PsiExpr rhs){
      return new PsiExpr(dexpr.dIvr(DIvr.Type.eqZ, rhs._expression-_expression).simplify(one));
   }
   auto ne(PsiExpr rhs){
      return new PsiExpr(dexpr.dIvr(DIvr.Type.neqZ, rhs._expression-_expression).simplify(one));
   }


   auto lt(PsiExpr rhs) {
      return new PsiExpr(dexpr.dIvr(DIvr.Type.lZ, _expression-rhs._expression).simplify(one));
   }

   auto le(PsiExpr rhs){
      return new PsiExpr(dexpr.dIvr(DIvr.Type.leZ, _expression-rhs._expression).simplify(one));
   }

   auto gt(PsiExpr rhs){
      return new PsiExpr(dexpr.dIvr(DIvr.Type.lZ, rhs._expression-_expression).simplify(one));
   }

   auto ge(PsiExpr rhs){
      return new PsiExpr(dexpr.dIvr(DIvr.Type.leZ, rhs._expression-_expression).simplify(one));
   }


   auto negate(){
      if (auto iv = cast(DIvr)_expression) {
         return new PsiExpr(dexpr.negateDIvr(iv));
      }
      else{
         auto s = format!"You can only negate Iverson brackets, %s is not a (pure) Iverson bracket"(_expression);
         throw new TypeError(s);
      }
   }


   auto filter_open_iverson(){
      auto result = _filter_open_iverson(_expression);
      return new PsiExpr(result);
   }



}



class Polynomial{
   PsiExpr _polynomial;

   this(PsiExpr expression,bool unsafe_init=false){
      if (unsafe_init) {
         _polynomial = expression;
      }
      else if (expression.is_polynomial) {
         _polynomial = expression;
      }
      else{
         auto s = format!"You're intialization expression (%s) is not a polynomial"(expression);
         throw new TypeError(s);
      }
   }

   auto is_zero(){
      return _polynomial._expression==zero;
   }
   auto is_one(){
      return _polynomial._expression==one;
   }

   override string toString(){
      return _polynomial.toString();
   }


   auto simplify(){
      auto expression = _polynomial.simplify();
      return  new Polynomial(expression , true);
   }

   auto to_PsiExpr(){
      return new PsiExpr(_polynomial._expression);
   }

   auto to_float(){
      auto q = cast(Dℚ)_polynomial._expression;
      return toReal(q.c);
      /* auto num = q.c.num.toLong();
      auto den = q.c.den.toLong();
      return num.to!real()/den.to!real(); */
   }

   auto variables(){
      PsiExpr[] variables;
      foreach(v;_polynomial._expression.freeVars){
         variables ~= new PsiExpr(v);
      }
      return variables;
   }



   auto opBinary(string op)(Polynomial rhs) if(op == "+"){
      return new Polynomial(_polynomial + rhs._polynomial);
   }
   auto opBinary(string op)(Polynomial rhs) if(op == "-"){
      return new Polynomial(_polynomial - rhs._polynomial);
   }
   auto opBinary(string op)(Polynomial rhs) if(op == "*"){
      return new Polynomial(_polynomial * rhs._polynomial);
   }


   auto factorize_list(){
      /* TODO make this actually do anything smart */
      auto factor_list = _factors(_polynomial._expression);
      Polynomial[] result;
      foreach(f;factor_list){
         result ~= new Polynomial(new PsiExpr(f));
      }
      return result;
   }

   auto get_terms(){
      auto terms = _terms(_polynomial._expression);
      Polynomial[] result;
      foreach(t;terms){
         result ~= new Polynomial(new PsiExpr(t));
      }
      return result;
   }

   /* auto integrate(PsiExpr variable, PsiExpr lb, PsiExpr ub, EvalBoundsCache register){
      return _integrate(variable, lb, ub, register);
   } */

   auto integrate(Polynomial variable, Polynomial lb, Polynomial ub, EvalBoundsCache register){
      return _integrate(variable._polynomial, lb._polynomial, ub._polynomial, register);
   }


   auto _integrate(PsiExpr variable, PsiExpr lb, PsiExpr ub, EvalBoundsCache register){
      auto v = variable._expression.toString().dVar;

      auto poly = _polynomial._expression.asPolynomialIn(v);

		DExprSet s;
      DExpr lb_eval;
      DExpr ub_eval;
		foreach(i,coeff;poly.coefficients){
			assert(i<size_t.max);

         if (!lb._expression.hasFreeVars()){
            lb_eval = register.retrieve_cache(lb._expression, i+1);
         }
         else{
            lb_eval = lb._expression^^(i+1);
         }
         if (!ub._expression.hasFreeVars()){
            ub_eval = register.retrieve_cache(ub._expression, i+1);
         }
         else{
            ub_eval = ub._expression^^(i+1);
         }


			DPlus.insert(s, (coeff/(i+1)).simplify(one) * ( ub_eval - lb_eval ) );
		}
		auto result =  dPlus(s);

      return new Polynomial(new PsiExpr(result.simplify(one)), true);
   }


   auto as_poly_in(PsiExpr variable){
      auto v = variable._expression.toString().dVar;
      auto expr = _polynomial._expression.asPolynomialIn(v).toDExpr();
      return new Polynomial(new PsiExpr(expr));
   }

   auto normalize_in(PsiExpr variable){
      auto v = variable._expression.toString().dVar;
      auto expr = _polynomial._expression.polyNormalize(v);
      return new Polynomial(new PsiExpr(expr));
   }

}


class PiecewisePolynomial{
   PsiExpr _piecewise_polynomial;

   this(PsiExpr expression){
      // TODO check wheter is actually is a piecewise polynomial
      _piecewise_polynomial = expression.filter_open_iverson();
   }


   auto is_zero(){
      return _piecewise_polynomial._expression==zero;
   }
   auto is_one(){
      return _piecewise_polynomial._expression==one;
   }

   override string toString(){
      return _piecewise_polynomial.toString();
   }


   auto simplify(){
      auto expression = _piecewise_polynomial.simplify();
      return  new PiecewisePolynomial(expression);
   }

   auto filter_iverson(){
      auto filtered = _filter_iverson_epxr(_piecewise_polynomial._expression);
      return new PiecewisePolynomial(new PsiExpr(filtered));
   }

   auto to_PsiExpr(){
      return new PsiExpr(_piecewise_polynomial._expression);
   }


   auto opBinary(string op)(PiecewisePolynomial rhs) if(op == "+"){
      return new PiecewisePolynomial(_piecewise_polynomial + rhs._piecewise_polynomial);
   }
   auto opBinary(string op)(PiecewisePolynomial rhs) if(op == "-"){
      return new PiecewisePolynomial(_piecewise_polynomial - rhs._piecewise_polynomial);
   }
   auto opBinary(string op)(PiecewisePolynomial rhs) if(op == "*"){
      return new PiecewisePolynomial(_piecewise_polynomial * rhs._piecewise_polynomial);
   }


   auto eq(PiecewisePolynomial rhs){
      auto ex_lhs = _piecewise_polynomial._expression;
      auto ex_rhs = rhs._piecewise_polynomial._expression;
      return new PiecewisePolynomial(new PsiExpr( dexpr.dIvr(DIvr.Type.eqZ, (ex_rhs-ex_lhs).simplify(one))));
   }
   auto ne(PiecewisePolynomial rhs){
      auto ex_lhs = _piecewise_polynomial._expression;
      auto ex_rhs = rhs._piecewise_polynomial._expression;
      return new PiecewisePolynomial(new PsiExpr(dexpr.dIvr(DIvr.Type.neqZ, (ex_rhs-ex_lhs).simplify(one))));
   }


   auto lt(PiecewisePolynomial rhs){
      auto ex_lhs = _piecewise_polynomial._expression;
      auto ex_rhs = rhs._piecewise_polynomial._expression;
      return new PiecewisePolynomial(new PsiExpr(dexpr.dIvr(DIvr.Type.lZ, (ex_lhs-ex_rhs).simplify(one))));
   }

   auto le(PiecewisePolynomial rhs){
      auto ex_lhs = _piecewise_polynomial._expression;
      auto ex_rhs = rhs._piecewise_polynomial._expression;
      return new PiecewisePolynomial(new PsiExpr(dexpr.dIvr(DIvr.Type.leZ, (ex_lhs-ex_rhs).simplify(one))));
   }

   auto gt(PiecewisePolynomial rhs){
      auto ex_lhs = _piecewise_polynomial._expression;
      auto ex_rhs = rhs._piecewise_polynomial._expression;
      return new PiecewisePolynomial(new PsiExpr(dexpr.dIvr(DIvr.Type.lZ, (ex_rhs-ex_lhs).simplify(one))));
   }

   auto ge(PiecewisePolynomial rhs){
      auto ex_lhs = _piecewise_polynomial._expression;
      auto ex_rhs = rhs._piecewise_polynomial._expression;
      return new PiecewisePolynomial(new PsiExpr(dexpr.dIvr(DIvr.Type.leZ, (ex_rhs-ex_lhs).simplify(one))));
   }

   auto variables(){
      PsiExpr[] variables;
      foreach(v;_piecewise_polynomial._expression.freeVars){
         variables ~= new PsiExpr(v);
      }
      return variables;
   }

   auto integrate(PiecewisePolynomial variable){
      auto v = variable._piecewise_polynomial._expression.toString().dVar;
      auto result =  dInt(v, _piecewise_polynomial._expression);
      result  = _filter_open_iverson(result.simplify(one));
      return new PiecewisePolynomial(new PsiExpr(result));
   }
}




dexpr.DExpr _filter_open_iverson(dexpr.DExpr expression){
   if(auto dsum=cast(DPlus)expression){
      auto result = zero;
      foreach(s;dsum.summands()){
         result = result+_filter_open_iverson(s);
      }
      return result;
   }
   else if(auto dmult=cast(DMult)expression){
      auto result = one;
      foreach(f;dmult.factors()){
         result = result*_filter_open_iverson(f);
      }
      return result;
   }
   else if(auto iv=cast(DIvr)expression){
      if (iv.type==DIvr.Type.neqZ){
         return one;
      }
      if (iv.type==DIvr.Type.eqZ){
         return zero;
      }
      else{
         return expression;
      }
   }
   else{
      return expression;
   }
}



auto _filter_iverson_epxr(dexpr.DExpr expression){
   if(isPolynomial(expression)){
      return expression;
   }
   else if(auto iv=cast(DIvr)expression){
      return one;
   }
   else if(auto dsum=cast(DPlus)expression){
      auto result = zero;
      foreach(s;dsum.summands()){
         result = result+_filter_iverson_epxr(s);
      }
      return result;
   }
   else if(auto dmult=cast(DMult)expression){
      auto result = one;
      foreach(f;dmult.factors()){
         result = result*_filter_iverson_epxr(f);
      }
      return result;
   }
   else{
      return expression;
   }
}


auto _terms(dexpr.DExpr expression){
   dexpr.DExpr[] terms;
   if(auto dsum=cast(DPlus)expression){
      foreach(s;expression.summands){
         terms ~= s;
      }
   }
   else{
      terms ~= expression;
   }
   return terms;
}

auto _factors(dexpr.DExpr expression){
   dexpr.DExpr[] factors;
   if (auto dmul=cast(DMult)expression){
      foreach(f;expression.factors){
         factors ~= f;
      }
   }
   else{
      factors ~= expression;
   }
   return factors;
}












extern(C) void PydMain() {
   def!(S)();

   def!(toSympyString)();


   module_init();

   wrap_class!(
      EvalBoundsCache,
   )();


   wrap_class!(
      PsiExpr,
      Init!(dexpr.DExpr),

      Repr!(PsiExpr.toString),

      Property!(PsiExpr.variables),


      Property!(PsiExpr.is_zero),
      Property!(PsiExpr.is_one),
      Property!(PsiExpr.is_iverson),

      Def!(PsiExpr.is_equal),

      Def!(PsiExpr.simplify),

      OpBinary!("+"),
      OpBinary!("-"),
      OpBinary!("*"),
      OpBinary!("/"),
      OpBinary!("^^"),

      Def!(PsiExpr.eq),
      Def!(PsiExpr.ne),

      Def!(PsiExpr.lt),
      Def!(PsiExpr.le),
      Def!(PsiExpr.gt),
      Def!(PsiExpr.ge),

      Def!(PsiExpr.negate),

      Def!(PsiExpr.filter_open_iverson),

   )();


   wrap_class!(
      Polynomial,
      Init!(PsiExpr,bool),

      Repr!(Polynomial.toString),

      Property!(Polynomial.is_zero),
      Property!(Polynomial.is_one),

      Def!(Polynomial.simplify),
      Def!(Polynomial.to_float),

      Def!(Polynomial.to_PsiExpr),

      OpBinary!("+"),
      OpBinary!("-"),
      OpBinary!("*"),


      Def!(Polynomial.factorize_list),
      Def!(Polynomial.get_terms),


      Def!(Polynomial.integrate),

      Def!(Polynomial.as_poly_in),
      Def!(Polynomial.normalize_in),




      Property!(Polynomial.variables),

   )();

   wrap_class!(
      PiecewisePolynomial,
      Init!(PsiExpr),

      Repr!(PiecewisePolynomial.toString),

      Property!(PiecewisePolynomial.is_zero),
      Property!(PiecewisePolynomial.is_one),

      Def!(PiecewisePolynomial.simplify),
      Def!(PiecewisePolynomial.to_PsiExpr),

      OpBinary!("+"),
      OpBinary!("-"),
      OpBinary!("*"),

      Def!(PiecewisePolynomial.eq),
      Def!(PiecewisePolynomial.ne),

      Def!(PiecewisePolynomial.lt),
      Def!(PiecewisePolynomial.le),
      Def!(PiecewisePolynomial.gt),
      Def!(PiecewisePolynomial.ge),

      Def!(PiecewisePolynomial.integrate),

      Property!(PiecewisePolynomial.variables),


   )();



   wrap_class!(
      DExpr,
      Repr!(DExpr.toString)
   )();

}
